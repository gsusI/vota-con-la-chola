// Reassemble complete, immutable files split for the static host's size budget.
export async function loadHistoryFile(base, release, name) {
  const compressed = release.file_encodings?.[name] === 'gzip' || (release.compressed_xml && name.endsWith('.xml'));
  const parts = release.file_parts?.[name] || [{ path: name + (compressed ? '.gz' : '') }];
  const chunks = [];
  for (const part of parts) {
    const response = await fetch(`${base}${part.path}`, { cache: 'force-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (part.bytes !== undefined && bytes.length !== part.bytes) throw new Error('Incomplete history file');
    if (part.sha256) {
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (n) => n.toString(16).padStart(2, '0')).join('');
      if (hash !== part.sha256) throw new Error('History checksum mismatch');
    }
    chunks.push(bytes);
  }
  const blob = new Blob(chunks);
  return compressed ? new Response(blob.stream().pipeThrough(new DecompressionStream('gzip'))).blob() : blob;
}
