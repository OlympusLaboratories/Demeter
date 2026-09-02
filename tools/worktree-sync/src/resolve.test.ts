import { describe, expect, it } from 'vitest';
import {
  isPathWithin,
  parseSessionTail,
  resolveWorktreeForCwd,
  sessionAliases,
  splitTail,
} from './resolve';

const REPO = '/Users/d/gridmatic-dev';
const WT = '/Users/d/gridmatic-dev/.claude/worktrees/dylan/PLAT-2401';

const aiTitle = (t: string) => JSON.stringify({ type: 'ai-title', aiTitle: t, sessionId: 's1' });
const customTitle = (t: string) =>
  JSON.stringify({ type: 'custom-title', customTitle: t, sessionId: 's1' });
const message = (cwd: string) => JSON.stringify({ type: 'user', cwd, sessionId: 's1' });
const worktreeState = (p: string | null) =>
  JSON.stringify({
    type: 'worktree-state',
    worktreeSession: p === null ? null : { worktreePath: p, worktreeName: 'PLAT-2401' },
    sessionId: 's1',
  });

describe('parseSessionTail', () => {
  it('reads the ai-title verbatim as the tab label', () => {
    const facts = parseSessionTail([message(REPO), aiTitle('PLAT-2364 rdev BigQuery permissions')]);
    expect(facts.aiTitle).toBe('PLAT-2364 rdev BigQuery permissions');
  });

  it('reads a custom-title from a manually renamed tab', () => {
    const facts = parseSessionTail([message(REPO), customTitle('PLAT-2407')]);
    expect(facts.customTitle).toBe('PLAT-2407');
  });

  it('keeps both titles when a session has each', () => {
    const facts = parseSessionTail([aiTitle('PLAT-2406 fix'), customTitle('PLAT-2406')]);
    expect(facts.aiTitle).toBe('PLAT-2406 fix');
    expect(facts.customTitle).toBe('PLAT-2406');
  });

  it('captures the worktree name alongside its path', () => {
    const facts = parseSessionTail([worktreeState(WT), aiTitle('anything')]);
    expect(facts.worktreeName).toBe('PLAT-2401');
  });

  it('prefers worktree-state over the message cwd', () => {
    const facts = parseSessionTail([
      message(REPO),
      worktreeState(WT),
      aiTitle('PLAT-2401'),
      message(REPO),
    ]);
    expect(facts.worktreePath).toBe(WT);
    expect(facts.source).toBe('worktree-state');
  });

  it('falls back to the newest message cwd when no worktree records exist', () => {
    const facts = parseSessionTail([message('/tmp/old'), aiTitle('Chat'), message(REPO)]);
    expect(facts.worktreePath).toBe(REPO);
    expect(facts.source).toBe('cwd');
  });

  it('treats a null worktreeSession as having left the worktree', () => {
    const facts = parseSessionTail([
      worktreeState(WT),
      worktreeState(null),
      aiTitle('PLAT-2401'),
      message(REPO),
    ]);
    expect(facts.worktreePath).toBe(REPO);
    expect(facts.source).toBe('cwd');
  });

  it('prefers relocated over the message cwd', () => {
    const facts = parseSessionTail([
      message(REPO),
      JSON.stringify({ type: 'relocated', relocatedCwd: WT, sessionId: 's1' }),
      aiTitle('PLAT-2401'),
    ]);
    expect(facts.worktreePath).toBe(WT);
    expect(facts.source).toBe('relocated');
  });

  it('tolerates both compact and spaced JSON encodings', () => {
    const spaced = '{"type": "ai-title", "aiTitle": "PLAT-2401", "sessionId": "s1"}';
    const compact = '{"type":"ai-title","aiTitle":"PLAT-2401","sessionId":"s1"}';
    expect(parseSessionTail([spaced]).aiTitle).toBe('PLAT-2401');
    expect(parseSessionTail([compact]).aiTitle).toBe('PLAT-2401');
  });

  it('ignores malformed lines without throwing', () => {
    const facts = parseSessionTail(['{"type":"ai-title", tru', '', aiTitle('PLAT-2401')]);
    expect(facts.aiTitle).toBe('PLAT-2401');
  });

  it('reports nothing for a session with no title', () => {
    expect(parseSessionTail([message(REPO)]).aiTitle).toBeUndefined();
  });
});

describe('sessionAliases', () => {
  it('offers the custom title, ai title and worktree name as title-then-name aliases', () => {
    const facts = parseSessionTail([worktreeState(WT), aiTitle('PLAT-2406 fix'), customTitle('Renamed')]);
    expect(sessionAliases(facts)).toEqual([
      { value: 'Renamed', kind: 'title' },
      { value: 'PLAT-2406 fix', kind: 'title' },
      { value: 'PLAT-2401', kind: 'name' },
    ]);
  });

  it('matches a tab named after its worktree even when the ai title differs', () => {
    const facts = parseSessionTail([worktreeState(WT), aiTitle('PLAT-2406 fix')]);
    expect(sessionAliases(facts).map((a) => a.value)).toContain('PLAT-2401');
  });

  it('matches a manually renamed tab that never got an ai title', () => {
    const facts = parseSessionTail([worktreeState(WT), customTitle('PLAT-2407')]);
    expect(sessionAliases(facts)[0]).toEqual({ value: 'PLAT-2407', kind: 'title' });
  });

  it('falls back to the worktree directory name when no worktree-state exists', () => {
    const facts = parseSessionTail([
      JSON.stringify({ type: 'relocated', relocatedCwd: WT, sessionId: 's1' }),
    ]);
    expect(sessionAliases(facts)).toEqual([{ value: 'PLAT-2401', kind: 'name' }]);
  });

  it('does not repeat an alias that two sources agree on', () => {
    const facts = parseSessionTail([worktreeState(WT), aiTitle('PLAT-2401')]);
    expect(sessionAliases(facts)).toEqual([{ value: 'PLAT-2401', kind: 'title' }]);
  });

  it('is empty for a session with no title and no worktree', () => {
    expect(sessionAliases(parseSessionTail([]))).toEqual([]);
  });
});

describe('splitTail', () => {
  it('drops the leading partial line when the read started mid-file', () => {
    expect(splitTail('e":"user"}\n{"a":1}', true)).toEqual(['{"a":1}']);
  });

  it('keeps every line when the whole file was read', () => {
    expect(splitTail('{"a":1}\n{"b":2}', false)).toEqual(['{"a":1}', '{"b":2}']);
  });
});

describe('isPathWithin', () => {
  it('matches a directory against itself', () => {
    expect(isPathWithin(REPO, REPO)).toBe(true);
  });

  it('matches a nested path', () => {
    expect(isPathWithin(REPO, `${REPO}/apps/rdev`)).toBe(true);
  });

  it('does not match a sibling sharing a name prefix', () => {
    expect(isPathWithin('/a/b', '/a/bc')).toBe(false);
  });

  it('does not match a parent against its child', () => {
    expect(isPathWithin(`${REPO}/apps`, REPO)).toBe(false);
  });
});

describe('resolveWorktreeForCwd', () => {
  const known = [REPO, WT];

  it('picks the worktree over the repo root that contains it', () => {
    expect(resolveWorktreeForCwd(WT, known)).toBe(WT);
  });

  it('picks the worktree for a subdirectory inside it', () => {
    expect(resolveWorktreeForCwd(`${WT}/apps/iam`, known)).toBe(WT);
  });

  it('picks the repo root for a path outside every worktree', () => {
    expect(resolveWorktreeForCwd(`${REPO}/apps/rdev`, known)).toBe(REPO);
  });

  it('returns undefined for an unrelated path', () => {
    expect(resolveWorktreeForCwd('/tmp/elsewhere', known)).toBeUndefined();
  });
});
