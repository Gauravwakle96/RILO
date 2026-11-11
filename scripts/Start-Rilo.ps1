param(
    [int]$Port = 8018,
    [switch]$SkipBuild,
    [switch]$Gateway
)
$ErrorActionPreference = 'Stop'
$riloProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $riloProjectRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/'
}
uv sync --locked
if ($LASTEXITCODE -ne 0) { throw 'Python dependency setup failed.' }
npm ci --prefix backend/rilo/promptfoo_runtime --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Promptfoo assertion engine setup failed.' }

if (-not $SkipBuild) {
    npm ci --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency setup failed.' }
    npm run build --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}

$riloGatewayProcess = $null
if ($Gateway) {
    $riloGatewayListening = Get-NetTCPConnection -LocalPort 8086 -State Listen -ErrorAction SilentlyContinue
    if (-not $riloGatewayListening) {
        uv run python scripts/setup_gateway.py
        if ($LASTEXITCODE -ne 0) { throw 'Gateway setup failed.' }
        $riloGatewayArgs = @('run', 'python', 'scripts/setup_gateway.py', '--start', '--port', '8086')
        $riloGatewayProcess = Start-Process -FilePath 'uv' -ArgumentList $riloGatewayArgs -WorkingDirectory $riloProjectRoot -WindowStyle Hidden -PassThru
        $riloGatewayDeadline = [DateTime]::UtcNow.AddSeconds(25)
        do {
            if ($riloGatewayProcess.HasExited) { throw 'The local gateway did not start.' }
            $riloGatewayReady = Get-NetTCPConnection -LocalPort 8086 -State Listen -ErrorAction SilentlyContinue
            if ($riloGatewayReady) { break }
            Start-Sleep -Milliseconds 250
        } while ([DateTime]::UtcNow -lt $riloGatewayDeadline)
        if (-not $riloGatewayReady) { throw 'Gateway startup timed out. Inspect local gateway logs.' }
    }
}
try {
    uv run rilo serve --port $Port
} finally {
    if ($riloGatewayProcess -and -not $riloGatewayProcess.HasExited) {
        taskkill /PID $riloGatewayProcess.Id /T /F 2>$null | Out-Null
    }
}
