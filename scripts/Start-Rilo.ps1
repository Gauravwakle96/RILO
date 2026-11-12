param(
    [int]$Port = 8018,
    [switch]$SkipBuild,
    [switch]$Gateway,
    [switch]$Update,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$riloProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $riloProjectRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/'
}
if ($Update -or -not (Test-Path -LiteralPath '.venv')) {
    uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency setup failed.' }
}
if ($Update -or -not (Test-Path -LiteralPath 'backend/rilo/promptfoo_runtime/node_modules/promptfoo/package.json')) {
    npm ci --prefix backend/rilo/promptfoo_runtime --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Promptfoo assertion engine setup failed.' }
}

if (-not $SkipBuild -and ($Update -or -not (Test-Path -LiteralPath 'frontend/dist/index.html'))) {
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
    if ($NoBrowser) { uv run --no-sync rilo serve --port $Port }
    else { uv run --no-sync rilo serve --port $Port --open }
} finally {
    if ($riloGatewayProcess -and -not $riloGatewayProcess.HasExited) {
        taskkill /PID $riloGatewayProcess.Id /T /F 2>$null | Out-Null
    }
}
