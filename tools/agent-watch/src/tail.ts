import * as fs from 'node:fs/promises';
import { type TranscriptLine } from './transcript';

export interface TailState {
  offset: number;
  partial: string;
  lines: TranscriptLine[];
}

export function emptyTail(): TailState {
  return { offset: 0, partial: '', lines: [] };
}

export function appendChunk(state: TailState, chunk: string): TailState {
  const combined = state.partial + chunk;
  const parts = combined.split('\n');
  state.partial = parts.pop() ?? '';
  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    try {
      state.lines.push(JSON.parse(trimmed) as TranscriptLine);
    } catch {
      continue;
    }
  }
  return state;
}

export class TranscriptCache {
  private states = new Map<string, TailState>();

  async read(filePath: string): Promise<TranscriptLine[]> {
    let state = this.states.get(filePath);
    if (!state) {
      state = emptyTail();
      this.states.set(filePath, state);
    }

    let size: number;
    try {
      size = (await fs.stat(filePath)).size;
    } catch {
      this.states.delete(filePath);
      return [];
    }

    if (size < state.offset) {
      state.offset = 0;
      state.partial = '';
      state.lines = [];
    }

    if (size === state.offset) return state.lines;

    const length = size - state.offset;
    let handle: fs.FileHandle | undefined;
    try {
      handle = await fs.open(filePath, 'r');
      const buffer = Buffer.alloc(length);
      const { bytesRead } = await handle.read(buffer, 0, length, state.offset);
      appendChunk(state, buffer.subarray(0, bytesRead).toString('utf8'));
      state.offset += bytesRead;
    } catch {
      return state.lines;
    } finally {
      await handle?.close().catch(() => undefined);
    }

    return state.lines;
  }

  bytesRead(filePath: string): number {
    return this.states.get(filePath)?.offset ?? 0;
  }

  forget(filePath: string): void {
    this.states.delete(filePath);
  }

  clear(): void {
    this.states.clear();
  }
}
