// Download utilities for file exports

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadJson(data, filename = 'export.json') {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  downloadBlob(blob, filename);
}

export function downloadSvg(svgEl, filename = 'export.svg') {
  const serializer = new XMLSerializer();
  const svgStr = serializer.serializeToString(svgEl);
  const blob = new Blob([svgStr], { type: 'image/svg+xml' });
  downloadBlob(blob, filename);
}

export function downloadText(text, filename = 'export.txt', mimeType = 'text/plain') {
  const blob = new Blob([text], { type: mimeType });
  downloadBlob(blob, filename);
}

export async function downloadUrl(url, filename) {
  const res = await fetch(url);
  const blob = await res.blob();
  downloadBlob(blob, filename);
}
