export const PREVIEW_LINES = 20;
export const PREVIEW_CHARS = 1600;

export interface Preview {
  head: string;
  clipped: boolean;
  hiddenLines: number;
  hiddenChars: number;
}

export function previewOf(body: string, maxLines = PREVIEW_LINES, maxChars = PREVIEW_CHARS): Preview {
  const lines = body.split('\n');
  let head = lines.slice(0, Math.max(1, maxLines)).join('\n');
  if (head.length > maxChars) head = head.slice(0, Math.max(1, maxChars));

  if (head.length === body.length) {
    return { head: body, clipped: false, hiddenLines: 0, hiddenChars: 0 };
  }

  return {
    head,
    clipped: true,
    hiddenLines: lines.length - head.split('\n').length,
    hiddenChars: body.length - head.length,
  };
}

export function moreLabel(preview: Preview): string {
  if (preview.hiddenLines > 0) {
    return `Show more (${preview.hiddenLines.toLocaleString()} more lines)`;
  }
  return `Show more (${preview.hiddenChars.toLocaleString()} more characters)`;
}
