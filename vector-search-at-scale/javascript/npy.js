// Minimal reader/writer for NumPy .npy files holding a 2-D float32 matrix.
// Lets the Python and JavaScript demos share one embeddings.npy file.
import { readFileSync, writeFileSync } from "node:fs";

const MAGIC = Buffer.from([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59]); // "\x93NUMPY"

/** Returns { data: Float32Array (row-major), rows, cols }. */
export function readNpy(path) {
  const buf = readFileSync(path);
  if (!buf.subarray(0, 6).equals(MAGIC)) throw new Error(`${path} is not a .npy file`);
  const major = buf[6];
  const headerLength = major === 1 ? buf.readUInt16LE(8) : buf.readUInt32LE(8);
  const headerStart = major === 1 ? 10 : 12;
  const header = buf.toString("latin1", headerStart, headerStart + headerLength);
  if (!header.includes("'descr': '<f4'")) throw new Error(`Expected little-endian float32, got: ${header}`);
  if (header.includes("'fortran_order': True")) throw new Error("Fortran-order arrays are not supported");
  const [rows, cols] = header.match(/'shape': \((\d+), (\d+)\)/).slice(1).map(Number);

  const offset = headerStart + headerLength;
  const bytes = buf.subarray(offset, offset + rows * cols * 4);
  // Copy into an aligned buffer so Float32Array can view it safely.
  const data = new Float32Array(rows * cols);
  new Uint8Array(data.buffer).set(bytes);
  return { data, rows, cols };
}

/** Writes a row-major Float32Array as a (rows, cols) float32 .npy file (format version 1.0). */
export function writeNpy(path, data, rows, cols) {
  let header = `{'descr': '<f4', 'fortran_order': False, 'shape': (${rows}, ${cols}), }`;
  const unpadded = 10 + header.length + 1; // magic(6) + version(2) + length(2) + header + "\n"
  header += " ".repeat((64 - (unpadded % 64)) % 64) + "\n"; // NumPy pads the header to a multiple of 64 bytes
  const prefix = Buffer.alloc(10);
  MAGIC.copy(prefix, 0);
  prefix[6] = 1;
  prefix[7] = 0;
  prefix.writeUInt16LE(header.length, 8);
  writeFileSync(path, Buffer.concat([prefix, Buffer.from(header, "latin1"), Buffer.from(data.buffer, data.byteOffset, data.byteLength)]));
}
