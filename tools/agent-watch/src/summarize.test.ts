import { describe, expect, it } from 'vitest';
import { clip, resultToText, summarizeToolUse } from './summarize';

describe('summarizeToolUse', () => {
  it('summarizes each tool by the field a reader actually scans for', () => {
    expect(summarizeToolUse('Bash', { command: 'git status --short' })).toBe('git status --short');
    expect(summarizeToolUse('Read', { file_path: '/a/b/auth.ts' })).toBe('auth.ts');
    expect(summarizeToolUse('Read', { file_path: '/a/auth.ts', offset: 1, limit: 120 })).toBe('auth.ts:1-121');
    expect(summarizeToolUse('Grep', { pattern: 'validateToken', glob: '*.ts' })).toBe('validateToken in *.ts');
    expect(summarizeToolUse('Agent', { description: 'check auth', subagent_type: 'Explore' })).toBe(
      'check auth (Explore)',
    );
  });

  it('falls back to the first string argument for an unknown tool', () => {
    expect(summarizeToolUse('SomeNewTool', { payload: 'interesting value' })).toBe('interesting value');
    expect(summarizeToolUse('SomeNewTool', {})).toBe('');
  });

  it('collapses whitespace so a multi-line command stays one line', () => {
    expect(summarizeToolUse('Bash', { command: 'echo one\n  echo two' })).toBe('echo one echo two');
  });
});

describe('clip', () => {
  it('truncates with an ellipsis only past the limit', () => {
    expect(clip('short', 10)).toBe('short');
    expect(clip('abcdefghijkl', 5)).toBe('abcd…');
  });
});

describe('resultToText', () => {
  it('reads a plain string, a block array, and a single block', () => {
    expect(resultToText('plain')).toBe('plain');
    expect(resultToText([{ type: 'text', text: 'one' }, { type: 'text', text: 'two' }])).toBe('one\ntwo');
    expect(resultToText({ type: 'text', text: 'solo' })).toBe('solo');
    expect(resultToText(undefined)).toBe('');
  });
});
