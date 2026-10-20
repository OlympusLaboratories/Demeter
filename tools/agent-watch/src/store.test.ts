import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { Store, type StoreSettings } from './store';

const temps: string[] = [];

async function fixture(): Promise<{ projects: string; transcript: string; subagents: string }> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'agent-watch-store-'));
  temps.push(root);
  const projects = path.join(root, 'projects');
  const slug = '-tmp-repo';
  const sessionId = 'aaaaaaaa-1111-2222-3333-444444444444';
  const dir = path.join(projects, slug);
  const subagents = path.join(dir, sessionId, 'subagents');
  await fs.mkdir(subagents, { recursive: true });

  const transcript = path.join(dir, `${sessionId}.jsonl`);
  await fs.writeFile(
    transcript,
    `${JSON.stringify({ type: 'user', cwd: '/tmp/repo', gitBranch: 'main', message: { content: [{ type: 'text', text: 'hi' }] } })}\n`,
  );
  return { projects, transcript, subagents };
}

function settings(projects: string): StoreSettings {
  return {
    projectsDir: projects,
    liveWindowSeconds: 3600,
    recentDays: 3650,
    maxSessionsPerRepo: 12,
    pollSeconds: 2,
    statusBarPriority: 110,
    initialDepth: 1,
    zoomSensitivity: 1,
    hideDeletedWork: false,
  };
}

afterEach(async () => {
  while (temps.length > 0) {
    const dir = temps.pop();
    if (dir) await fs.rm(dir, { recursive: true, force: true });
  }
});

describe('Store', () => {
  it('discovers a repo, loads its session, and exposes what to watch', async () => {
    const { projects, transcript, subagents } = await fixture();
    const store = new Store(settings(projects));

    await store.discover();
    await store.loadSelected();
    const view = store.view(false);

    expect(view.repos).toHaveLength(1);
    expect(view.repos[0]?.label).toBe('repo');
    expect(view.worktrees).toHaveLength(1);
    expect(view.graph.nodes).toHaveLength(1);
    expect(view.graph.nodes[0]?.status).toBe('live');

    expect(store.watchTargets()).toContain(transcript);
    expect(store.watchTargets()).toContain(subagents);
  });

  it('drops a project directory that is not inside a git repository', async () => {
    const { projects } = await fixture();
    const store = new Store({ ...settings(projects), hideDeletedWork: true });

    await store.discover();
    await store.loadSelected();

    expect(store.view(false).repos).toHaveLength(0);
  });

  it('keeps that directory when the filter is turned off', async () => {
    const { projects } = await fixture();
    const store = new Store(settings(projects));

    await store.discover();
    await store.loadSelected();

    expect(store.view(false).repos).toHaveLength(1);
    expect(store.view(false).removedCount).toBe(0);
  });

  it('picks up a subagent that appears after the first load', async () => {
    const { projects, subagents } = await fixture();
    const store = new Store(settings(projects));

    await store.discover();
    await store.loadSelected();
    expect(store.view(false).graph.nodes).toHaveLength(1);

    await fs.writeFile(
      path.join(subagents, 'agent-a1.meta.json'),
      JSON.stringify({ agentType: 'Explore', description: 'look around', spawnDepth: 1 }),
    );
    await fs.writeFile(
      path.join(subagents, 'agent-a1.jsonl'),
      `${JSON.stringify({ type: 'assistant', message: { content: [{ type: 'text', text: 'found it' }] } })}\n`,
    );

    await store.discover();
    await store.loadSelected();
    const nodes = store.view(false).graph.nodes;

    expect(nodes).toHaveLength(2);
    expect(nodes.map((node) => node.label)).toContain('look around');
  });

  it('reflects transcript growth without re-reading from the start', async () => {
    const { projects, transcript } = await fixture();
    const store = new Store(settings(projects));

    await store.discover();
    await store.loadSelected();
    const before = store.view(false).graph.nodes[0]?.eventCount ?? 0;

    await fs.appendFile(
      transcript,
      `${JSON.stringify({ type: 'assistant', message: { content: [{ type: 'tool_use', id: 't1', name: 'Bash', input: { command: 'ls' } }] } })}\n`,
    );

    await store.loadSelected();
    expect(store.view(false).graph.nodes[0]?.eventCount).toBe(before + 1);
  });

  it('returns an empty view rather than throwing when the projects dir is missing', async () => {
    const store = new Store(settings('/definitely/not/here'));
    await store.discover();
    await store.loadSelected();

    const view = store.view(false);
    expect(view.repos).toEqual([]);
    expect(view.graph.nodes).toEqual([]);
    expect(view.watchedCount).toBe(0);
  });

  it('exposes the poll interval in milliseconds with a floor of one second', () => {
    expect(new Store({ ...settings('/x'), pollSeconds: 5 }).pollMs()).toBe(5000);
    expect(new Store({ ...settings('/x'), pollSeconds: 0 }).pollMs()).toBe(1000);
  });
});

describe('watch coverage', () => {
  it('watches each subagent transcript, not just the directory holding them', async () => {
    const { projects, subagents } = await fixture();
    await fs.writeFile(
      path.join(subagents, 'agent-a1.meta.json'),
      JSON.stringify({ agentType: 'Explore', description: 'look', spawnDepth: 1 }),
    );
    const agentTranscript = path.join(subagents, 'agent-a1.jsonl');
    await fs.writeFile(agentTranscript, `${JSON.stringify({ type: 'assistant', message: { content: [] } })}\n`);

    const store = new Store(settings(projects));
    await store.discover();
    await store.loadSelected();

    expect(store.watchTargets()).toContain(agentTranscript);
  });

  it('sees an existing subagent transcript grow, with no new files added', async () => {
    const { projects, subagents } = await fixture();
    await fs.writeFile(path.join(subagents, 'agent-a1.meta.json'), JSON.stringify({ description: 'look' }));
    const agentTranscript = path.join(subagents, 'agent-a1.jsonl');
    await fs.writeFile(agentTranscript, `${JSON.stringify({ type: 'assistant', message: { content: [] } })}\n`);

    const store = new Store(settings(projects));
    await store.discover();
    await store.loadSelected();
    const before = store.view(false).graph.nodes.find((node) => node.label === 'look')?.eventCount;

    await fs.appendFile(
      agentTranscript,
      `${JSON.stringify({ type: 'assistant', message: { content: [{ type: 'tool_use', id: 'x', name: 'Grep', input: { pattern: 'p' } }] } })}\n`,
    );
    await store.loadSelected();

    const after = store.view(false).graph.nodes.find((node) => node.label === 'look')?.eventCount;
    expect(after).toBe((before ?? 0) + 1);
  });
});

describe('progressive expansion', () => {
  async function wideFixture(): Promise<string> {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'agent-watch-wide-'));
    temps.push(root);
    const sessionId = 'cccccccc-1111-2222-3333-444444444444';
    const dir = path.join(root, 'projects', '-tmp-repo');
    const subagents = path.join(dir, sessionId, 'subagents');
    await fs.mkdir(subagents, { recursive: true });
    await fs.writeFile(
      path.join(dir, `${sessionId}.jsonl`),
      `${JSON.stringify({ type: 'user', cwd: '/tmp/repo', message: { content: [] } })}\n`,
    );
    for (let index = 0; index < 30; index += 1) {
      await fs.writeFile(
        path.join(subagents, `agent-a${index}.meta.json`),
        JSON.stringify({ description: `worker ${index}`, spawnDepth: 1 }),
      );
      await fs.writeFile(path.join(subagents, `agent-a${index}.jsonl`), '');
    }
    return path.join(root, 'projects');
  }

  it('starts a wide layer collapsed and opens it on toggle', async () => {
    const projects = await wideFixture();
    const store = new Store(settings(projects));
    await store.discover();
    await store.loadSelected();

    const collapsed = store.view(false).graph.nodes;
    expect(collapsed).toHaveLength(1);
    expect(collapsed[0]?.expanded).toBe(false);
    expect(collapsed[0]?.totalChildren).toBe(30);

    store.toggleNode(collapsed[0]!.id);
    const expanded = store.view(false).graph.nodes;
    expect(expanded).toHaveLength(31);

    store.toggleNode(collapsed[0]!.id);
    expect(store.view(false).graph.nodes).toHaveLength(1);
  });

  it('ignores a toggle on a leaf node', async () => {
    const { projects } = await fixture();
    const store = new Store(settings(projects));
    await store.discover();
    await store.loadSelected();

    const leaf = store.view(false).graph.nodes[0]!;
    expect(store.toggleNode(leaf.id)).toBe(false);
    expect(store.view(false).graph.nodes).toHaveLength(1);
  });

  it('forgets expansion when the repo changes', async () => {
    const projects = await wideFixture();
    const store = new Store(settings(projects));
    await store.discover();
    await store.loadSelected();

    const id = store.view(false).graph.nodes[0]!.id;
    store.toggleNode(id);
    expect(store.view(false).graph.nodes).toHaveLength(31);

    store.selectRepo('something-else');
    store.selectRepo('-tmp-repo');
    await store.loadSelected();
    expect(store.view(false).graph.nodes).toHaveLength(1);
  });

  it('reports a scope key that changes with the selected repo and worktree', async () => {
    const { projects } = await fixture();
    const store = new Store(settings(projects));
    await store.discover();
    await store.loadSelected();

    const before = store.view(false).scopeKey;
    store.selectRepo('other');
    expect(store.view(false).scopeKey).not.toBe(before);
  });
});
