export type DownloadProgress = { received: number; total: number | null };

const unavailable = 'A valid APK has not been uploaded yet. Add your signed APK at public/app.apk.';
const maxBytes = 256 * 1024 * 1024;

export function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// APKs are ZIP archives with an Android manifest. This rejects HTML fallbacks
// and text placeholders; Android must still verify the publisher's signature.
async function hasAndroidManifest(blob: Blob) {
  if (blob.size < 22) return false;
  const tail = new DataView(await blob.slice(-65557).arrayBuffer());
  for (let offset = tail.byteLength - 22; offset >= 0; offset--) {
    if (tail.getUint32(offset, true) !== 0x06054b50) continue;
    if (offset + 22 + tail.getUint16(offset + 20, true) !== tail.byteLength) continue;
    const directorySize = tail.getUint32(offset + 12, true);
    const directoryOffset = tail.getUint32(offset + 16, true);
    const entries = tail.getUint16(offset + 10, true);
    if (!entries || directoryOffset + directorySize > blob.size || directorySize > 16 * 1024 * 1024) return false;
    const directory = new DataView(await blob.slice(directoryOffset, directoryOffset + directorySize).arrayBuffer());
    const decoder = new TextDecoder();
    let cursor = 0;
    for (let entry = 0; entry < entries; entry++) {
      if (cursor + 46 > directory.byteLength || directory.getUint32(cursor, true) !== 0x02014b50) return false;
      const nameLength = directory.getUint16(cursor + 28, true);
      const extraLength = directory.getUint16(cursor + 30, true);
      const commentLength = directory.getUint16(cursor + 32, true);
      const next = cursor + 46 + nameLength + extraLength + commentLength;
      if (next > directory.byteLength) return false;
      const name = decoder.decode(new Uint8Array(directory.buffer, cursor + 46, nameLength));
      if (name === 'AndroidManifest.xml') return true;
      cursor = next;
    }
    return false;
  }
  return false;
}

export async function fetchApk(url: string, signal: AbortSignal, onProgress: (progress: DownloadProgress) => void) {
  const response = await fetch(url, { signal, cache: 'no-store', credentials: 'same-origin' });
  if (response.status === 403 && response.headers.get('content-type')?.includes('application/json')) {
    const detail: unknown = await response.json().catch(() => null);
    if (detail && typeof detail === 'object' && 'error' in detail && typeof detail.error === 'string') {
      throw new Error(detail.error.slice(0, 300));
    }
  }
  if (!response.ok || response.headers.get('content-type')?.includes('text/html')) throw new Error(unavailable);
  const length = Number(response.headers.get('content-length'));
  const total = length > 0 && !response.headers.get('content-encoding') ? length : null;
  if (total && total > maxBytes) throw new Error('The APK is too large for this download flow. Maximum size: 256 MB.');
  onProgress({ received: 0, total });
  let blob: Blob;
  if (response.body) {
    const reader = response.body.getReader();
    const chunks: ArrayBuffer[] = [];
    let received = 0;
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        received += value.byteLength;
        if (received > maxBytes) {
          await reader.cancel();
          throw new Error('The APK is too large. Maximum size: 256 MB.');
        }
        chunks.push(new Uint8Array(value).buffer);
        onProgress({ received, total });
      }
    } finally {
      reader.releaseLock();
    }
    blob = new Blob(chunks, { type: 'application/vnd.android.package-archive' });
  } else {
    blob = await response.blob();
    if (blob.size > maxBytes) throw new Error('The APK is too large. Maximum size: 256 MB.');
  }
  if (signal.aborted) throw new DOMException('Download cancelled', 'AbortError');
  if (!await hasAndroidManifest(blob)) throw new Error(unavailable);
  if (signal.aborted) throw new DOMException('Download cancelled', 'AbortError');
  onProgress({ received: blob.size, total: blob.size });
  return blob;
}

export function saveApk(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}