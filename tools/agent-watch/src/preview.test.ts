import { describe, expect, it } from 'vitest';
import { moreLabel, previewOf } from './preview';

describe('previewOf', () => {
  it('leaves a short body alone', () => {
    const preview = previewOf('one\ntwo', 20, 1600);
    expect(preview.clipped).toBe(false);
    expect(preview.head).toBe('one\ntwo');
    expect(preview.hiddenLines).toBe(0);
    expect(preview.hiddenChars).toBe(0);
  });

  it('keeps the body whole when it sits exactly on the line limit', () => {
    const body = Array.from({ length: 20 }, (_, index) => `line ${index}`).join('\n');
    expect(previewOf(body, 20, 1600).clipped).toBe(false);
  });

  it('clips to whole lines and counts what is held back', () => {
    const body = Array.from({ length: 50 }, (_, index) => `line ${index}`).join('\n');
    const preview = previewOf(body, 20, 1600);

    expect(preview.clipped).toBe(true);
    expect(preview.head.split('\n')).toHaveLength(20);
    expect(preview.head.startsWith('line 0')).toBe(true);
    expect(preview.hiddenLines).toBe(30);
    expect(body.startsWith(preview.head)).toBe(true);
  });

  it('clips a single enormous line by characters', () => {
    const body = 'x'.repeat(10_000);
    const preview = previewOf(body, 20, 1600);

    expect(preview.head).toHaveLength(1600);
    expect(preview.hiddenLines).toBe(0);
    expect(preview.hiddenChars).toBe(8400);
  });

  it('never loses a character between the head and what it reports hidden', () => {
    const body = `${'a'.repeat(900)}\n${'b'.repeat(900)}\n${'c'.repeat(900)}`;
    const preview = previewOf(body, 20, 1600);

    expect(preview.head.length + preview.hiddenChars).toBe(body.length);
  });

  it('names lines when it held back lines and characters when it held back one long line', () => {
    const byLines = previewOf(Array.from({ length: 50 }, () => 'line').join('\n'), 20, 1600);
    expect(moreLabel(byLines)).toBe('Show more (30 more lines)');

    const byChars = previewOf('y'.repeat(3000), 20, 1600);
    expect(moreLabel(byChars)).toBe('Show more (1,400 more characters)');
  });
});
