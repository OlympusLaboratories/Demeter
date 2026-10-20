import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { scanProjects, withinDays } from './discovery';

const temps: string[] = [];

async function makeProjects(): Promise<string> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'agent-watch-test-'));
  temps.push(root);
  return path.join(root, 'projects');
}

afterEach(async () => {
  while (temps.length > 0) {
    const dir = temps.pop();
    if (dir) await fs.rm(dir, { recursive: true, force: true });
  }
});

describe('scanProjects', () => {
  it('returns nothing for a missing directory instead of throwing', async () => {
    await expect(scanProjects('/definitely/not/here')).resolves.toEqual([]);
  });

  it('lists sessions newest first and skips dirs with no transcripts', async () => {
    const projects = await makeProjects();
    await fs.mkdir(path.join(projects, 'repo-a'), { recursive: true });
    await fs.mkdir(path.join(projects, 'repo-empty'), { recursive: true });
    await fs.writeFile(path.join(projects, 'repo-a', 'old.jsonl'), '{}\n');
    await fs.writeFile(path.join(projects, 'repo-a', 'new.jsonl'), '{}\n');
    await fs.utimes(path.join(projects, 'repo-a', 'old.jsonl'), new Date(1000), new Date(1000));

    const found = await scanProjects(projects);
    expect(found).toHaveLength(1);
    expect(found[0]?.slug).toBe('repo-a');
    expect(found[0]?.sessions.map((session) => session.sessionId)).toEqual(['new', 'old']);
  });

  it('skips symlinked project dirs so worktree aliases are not counted twice', async () => {
    const projects = await makeProjects();
    const real = path.join(projects, 'repo-main');
    await fs.mkdir(real, { recursive: true });
    await fs.writeFile(path.join(real, 'session.jsonl'), '{}\n');
    await fs.symlink(real, path.join(projects, 'repo-worktree-alias'), 'dir');

    const found = await scanProjects(projects);
    expect(found.map((project) => project.slug)).toEqual(['repo-main']);
  });
});

describe('withinDays', () => {
  it('bounds by whole days from now', () => {
    const now = 10 * 86_400_000;
    expect(withinDays(now - 86_400_000, 7, now)).toBe(true);
    expect(withinDays(now - 8 * 86_400_000, 7, now)).toBe(false);
  });
});
