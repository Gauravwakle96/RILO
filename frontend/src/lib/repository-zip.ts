// Stored ZIP entries; files remain data and are never executed during import.
const encoder = new TextEncoder();
const crcTable = Array.from({ length: 256 }, (_, i) => {
  let value = i;
  for (let j = 0; j < 8; j++)
    value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  return value >>> 0;
});
function crc(bytes: Uint8Array) {
  let value = 0xffffffff;
  for (const byte of bytes)
    value = crcTable[(value ^ byte) & 255] ^ (value >>> 8);
  return (value ^ 0xffffffff) >>> 0;
}
function header(size: number) {
  const data = new Uint8Array(size);
  return { data, view: new DataView(data.buffer) };
}
export async function repositoryZip(files: File[]) {
  if (!files.length || files.length > 2000)
    throw new Error("Select a folder with 1–2000 files.");
  const parts: Uint8Array<ArrayBuffer>[] = [];
  const central: Uint8Array<ArrayBuffer>[] = [];
  let offset = 0;
  let included = 0;
  let skipped = 0;
  for (const file of files) {
    const path = (file.webkitRelativePath || file.name)
      .split("/")
      .slice(file.webkitRelativePath ? 1 : 0)
      .join("/");
    const segments = path.split("/");
    if (
      segments.some((value) =>
        [
          ".git",
          "node_modules",
          ".venv",
          "venv",
          "dist",
          "build",
          "__pycache__",
          ".next",
          "vendor",
        ].includes(value),
      ) ||
      /(^|\/)\.env($|\.)/.test(path) ||
      /(^|\/)(id_rsa|id_ed25519)$|\.(pem|key|p12)$/i.test(path)
    ) {
      skipped++;
      continue;
    }
    if (
      !path ||
      path.length > 300 ||
      segments.some((value) => value === ".." || value === ".") ||
      /[\\:\0]/.test(path)
    )
      throw new Error("Folder contains an unsafe path.");
    if (file.size > 2_000_000)
      throw new Error(`${path} exceeds the 2 MB per-file limit.`);
    const name = encoder.encode(path);
    const data = new Uint8Array(await file.arrayBuffer());
    const checksum = crc(data);
    const local = header(30);
    local.view.setUint32(0, 0x04034b50, true);
    local.view.setUint16(4, 20, true);
    local.view.setUint16(6, 0x800, true);
    local.view.setUint32(14, checksum, true);
    local.view.setUint32(18, data.length, true);
    local.view.setUint32(22, data.length, true);
    local.view.setUint16(26, name.length, true);
    const entry = header(46);
    entry.view.setUint32(0, 0x02014b50, true);
    entry.view.setUint16(4, 20, true);
    entry.view.setUint16(6, 20, true);
    entry.view.setUint16(8, 0x800, true);
    entry.view.setUint32(16, checksum, true);
    entry.view.setUint32(20, data.length, true);
    entry.view.setUint32(24, data.length, true);
    entry.view.setUint16(28, name.length, true);
    entry.view.setUint32(42, offset, true);
    parts.push(local.data, name, data);
    central.push(entry.data, name);
    offset += 30 + name.length + data.length;
    included++;
    if (offset > 7_500_000)
      throw new Error(
        "Selected folder exceeds the bounded upload size. Choose a smaller source folder or ZIP.",
      );
  }
  if (!included)
    throw new Error(
      "No source files remain after excluding dependencies and credential files.",
    );
  const centralSize = central.reduce((sum, data) => sum + data.length, 0);
  const end = header(22);
  end.view.setUint32(0, 0x06054b50, true);
  end.view.setUint16(8, included, true);
  end.view.setUint16(10, included, true);
  end.view.setUint32(12, centralSize, true);
  end.view.setUint32(16, offset, true);
  const blob = new File(
    [...parts, ...central, end.data],
    "repository-folder.zip",
    { type: "application/zip" },
  );
  if (blob.size > 8_000_000)
    throw new Error("Folder archive exceeds the 8 MB upload limit.");
  return { file: blob, included, skipped };
}
