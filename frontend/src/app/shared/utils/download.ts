/**
 * Trigger a browser file download from in-memory data.
 */

export function downloadJson(data: unknown, filename: string): void {
  const json = JSON.stringify(data, null, 2);
  downloadText(json, filename, 'application/json');
}

export function downloadText(
  data: string,
  filename: string,
  mimeType = 'text/plain',
): void {
  const blob = new Blob([data], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
