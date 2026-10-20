import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { TranscriptCache, appendChunk, emptyTail } from './tail';

const temps: string[] = [];

async function tempFile(contents: string): Promise<string> {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'agent-watch-tail-'));
  temps.push(dir);
  const file = path.join(dir, 'session.jsonl');
  await fs.writeFile(file, contents);
  return file;
}

afterEach(async () => {
  while (temps.length > 0) {
    const dir = temps.pop();
    if (dir) await fs.rm(dir, { recursive: true, force: true });
  }
});

describe('appendChunk', () => {
  it('holds back a partial line until its newline arrives', () => {
    const state = emptyTail();
    appendChunk(state, '{"type":"a"}\n{"type":"b"');
    expect(state.lines).toHaveLength(1);
    expect(state.partial).toBe('{"type":"b"');

    appendChunk(state, '}\n');
    expect(state.lines.map((line) => line.type)).toEqual(['a', 'b']);
    expect(state.partial).toBe('');
  });

  it('skips malformed lines without losing the ones around them', () => {
    const state = emptyTail();
    appendChunk(state, '{"type":"a"}\nnot json\n{"type":"c"}\n');
    expect(state.lines.map((line) => line.type)).toEqual(['a', 'c']);
  });
});

describe('TranscriptCache', () => {
  it('reads only the appended bytes on a second pass', async () => {
    const file = await tempFile('{"type":"a"}\n');
    const cache = new TranscriptCache();

    expect(await cache.read(file)).toHaveLength(1);
    const afterFirst = cache.bytesRead(file);

    await fs.appendFile(file, '{"type":"b"}\n');
    const lines = await cache.read(file);

    expect(lines.map((line) => line.type)).toEqual(['a', 'b']);
    expect(cache.bytesRead(file)).toBeGreaterThan(afterFirst);
  });

  it('does no work when the file has not grown', async () => {
    const file = await tempFile('{"type":"a"}\n');
    const cache = new TranscriptCache();
    await cache.read(file);
    const offset = cache.bytesRead(file);
    await cache.read(file);
    expect(cache.bytesRead(file)).toBe(offset);
  });

  it('reparses from the start when a file shrinks', async () => {
    const file = await tempFile('{"type":"a"}\n{"type":"b"}\n');
    const cache = new TranscriptCache();
    expect(await cache.read(file)).toHaveLength(2);

    await fs.writeFile(file, '{"type":"z"}\n');
    const lines = await cache.read(file);
    expect(lines.map((line) => line.type)).toEqual(['z']);
  });

  it('returns nothing for a file that disappears', async () => {
    const file = await tempFile('{"type":"a"}\n');
    const cache = new TranscriptCache();
    await cache.read(file);
    await fs.rm(file);
    expect(await cache.read(file)).toEqual([]);
  });

  it('survives a transcript whose last line is still being written', async () => {
    const file = await tempFile('{"type":"a"}\n{"type":"partial"');
    const cache = new TranscriptCache();
    expect(await cache.read(file)).toHaveLength(1);

    await fs.appendFile(file, '}\n');
    expect(await cache.read(file)).toHaveLength(2);
  });
});
