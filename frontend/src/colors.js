// A small fixed palette, cycled by a stable hash of a string id/name - used
// to give each camera panel and each employee a consistent, distinct accent
// color without needing to store a color choice anywhere.
const PALETTE = ["#2563eb", "#7c3aed", "#0d9488", "#db2777", "#ea580c", "#65a30d"];

function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

export function colorFor(key) {
  return PALETTE[hashString(String(key)) % PALETTE.length];
}

export function initialsFor(name) {
  const parts = String(name).trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
