import { describe, expect, it } from 'vitest';
import {
  buildEvents,
  buildSessionTree,
  propagateActivity,
  waitingOn,
  completedToolUseIds,
  deriveLabel,
  erroredToolUseIds,
  spawnIdsIn,
} from './model';
import type { AgentNode, NodeStatus } from './model';
import type { TranscriptLine } from './transcript';

function assistant(blocks: unknown[]): TranscriptLine {
  return { type: 'assistant', message: { role: 'assistant', content: blocks as never } };
}

function user(blocks: unknown[]): TranscriptLine {
  return { type: 'user', message: { role: 'user', content: blocks as never } };
}

describe('buildEvents', () => {
  it('pairs a tool result with the tool call that produced it', () => {
    const events = buildEvents([
      assistant([{ type: 'tool_use', id: 'toolu_1', name: 'Bash', input: { command: 'git status' } }]),
      user([{ type: 'tool_result', tool_use_id: 'toolu_1', content: 'clean tree' }]),
    ]);

    expect(events).toHaveLength(1);
    expect(events[0]?.name).toBe('Bash');
    expect(events[0]?.summary).toBe('git status');
    expect(events[0]?.result).toBe('clean tree');
    expect(events[0]?.isError).toBe(false);
  });

  it('recovers a prompt stored as a plain string rather than a block list', () => {
    const events = buildEvents([
      { type: 'user', message: { role: 'user', content: 'fix the installer please' } },
    ]);

    expect(events).toHaveLength(1);
    expect(events[0]?.kind).toBe('text');
    expect(events[0]?.role).toBe('user');
    expect(events[0]?.text).toBe('fix the installer please');
  });

  it('tells your prompts apart from the agent own prose', () => {
    const events = buildEvents([
      user([{ type: 'text', text: 'why did it fail?' }]),
      assistant([{ type: 'text', text: 'because vsce refused the link' }]),
    ]);

    expect(events.map((event) => event.role)).toEqual(['user', 'assistant']);
  });

  it('marks injected context as context, not as something you said', () => {
    const events = buildEvents([
      { type: 'user', isMeta: true, message: { role: 'user', content: 'Base directory for this skill: /x' } },
    ]);

    expect(events[0]?.role).toBe('meta');
  });

  it('keeps an assistant text block whole, newlines and all', () => {
    const said = `First paragraph that runs on for a while.

    Second paragraph, indented, after a blank line.
${'x'.repeat(5000)}`;
    const events = buildEvents([assistant([{ type: 'text', text: said }])]);

    expect(events[0]?.kind).toBe('text');
    expect(events[0]?.text).toBe(said);
  });

  it('keeps a thinking block whole', () => {
    const thought = `Weighing it up.\n\n${'y'.repeat(9000)}`;
    const events = buildEvents([assistant([{ type: 'thinking', thinking: thought, signature: 'abc' }])]);

    expect(events[0]?.text).toBe(thought);
    expect(events[0]?.thinkingChars).toBe(thought.length);
  });

  it('keeps a tool result whole however large', () => {
    const output = 'line\n'.repeat(40_000);
    const events = buildEvents([
      assistant([{ type: 'tool_use', id: 'toolu_1', name: 'Bash', input: { command: 'cat big' } }]),
      user([{ type: 'tool_result', tool_use_id: 'toolu_1', content: output }]),
    ]);

    expect(events[0]?.result).toBe(output);
  });

  it('records an empty thinking block as withheld rather than dropping it', () => {
    const events = buildEvents([assistant([{ type: 'thinking', thinking: '', signature: 'abc' }])]);
    expect(events[0]?.kind).toBe('thinking');
    expect(events[0]?.text).toBeUndefined();
    expect(events[0]?.thinkingChars).toBe(0);
  });

  it('keeps thinking text when the API returned a summary', () => {
    const events = buildEvents([assistant([{ type: 'thinking', thinking: 'weighing two options', signature: 'x' }])]);
    expect(events[0]?.text).toBe('weighing two options');
    expect(events[0]?.thinkingChars).toBe(20);
  });

  it('marks an errored tool result', () => {
    const events = buildEvents([
      assistant([{ type: 'tool_use', id: 'toolu_2', name: 'Read', input: { file_path: '/a/b.ts' } }]),
      user([{ type: 'tool_result', tool_use_id: 'toolu_2', content: 'nope', is_error: true }]),
    ]);
    expect(events[0]?.isError).toBe(true);
    expect(events[0]?.summary).toBe('b.ts');
  });
});

describe('spawn indexing', () => {
  it('collects Agent and Task tool_use ids', () => {
    const ids = spawnIdsIn([
      assistant([
        { type: 'tool_use', id: 'toolu_a', name: 'Agent', input: { description: 'one' } },
        { type: 'tool_use', id: 'toolu_b', name: 'Task', input: { description: 'two' } },
        { type: 'tool_use', id: 'toolu_c', name: 'Bash', input: { command: 'ls' } },
      ]),
    ]);
    expect([...ids].sort()).toEqual(['toolu_a', 'toolu_b']);
  });

  it('reports which tool calls have completed', () => {
    const done = completedToolUseIds([user([{ type: 'tool_result', tool_use_id: 'toolu_a', content: 'ok' }])]);
    expect(done.has('toolu_a')).toBe(true);
    expect(done.has('toolu_b')).toBe(false);
  });
});

describe('buildSessionTree', () => {
  const base = {
    sessionId: 'abcdef12-0000-0000-0000-000000000000',
    mtimeMs: 1_000_000,
    liveWindowSeconds: 60,
    nowMs: 1_000_000,
    workflows: [],
  };

  it('names the session after the title shown on its editor tab', () => {
    const tree = buildSessionTree({
      ...base,
      lines: [{ type: 'ai-title', aiTitle: 'Herdr swarm observation setup' }],
      subagents: [],
    });

    expect(tree.label).toBe('Herdr swarm observation setup');
  });

  it('prefers a title you set by hand over one the model wrote later', () => {
    const tree = buildSessionTree({
      ...base,
      lines: [
        { type: 'ai-title', aiTitle: 'ticket context' },
        { type: 'custom-title', customTitle: 'PLAT-3138' },
        { type: 'ai-title', aiTitle: '/dev/shm size in rdev' },
      ],
      subagents: [],
    });

    expect(tree.label).toBe('PLAT-3138');
  });

  it('keeps the newest title of each kind', () => {
    const tree = buildSessionTree({
      ...base,
      lines: [
        { type: 'custom-title', customTitle: 'first name' },
        { type: 'custom-title', customTitle: 'renamed' },
      ],
      subagents: [],
    });

    expect(tree.label).toBe('renamed');
  });

  it('ignores a blank title and falls back to the session id', () => {
    const tree = buildSessionTree({
      ...base,
      lines: [{ type: 'custom-title', customTitle: '   ' }],
      subagents: [],
    });

    expect(tree.label).toBe('abcdef12');
  });

  it('attaches a subagent to the node whose transcript spawned it', () => {
    const tree = buildSessionTree({
      ...base,
      lines: [assistant([{ type: 'tool_use', id: 'toolu_x', name: 'Agent', input: { description: 'explore' } }])],
      subagents: [
        {
          agentId: 'a111',
          meta: { agentType: 'Explore', description: 'explore', toolUseId: 'toolu_x', spawnDepth: 1 },
          lines: [],
        },
      ],
    });

    expect(tree.children).toHaveLength(1);
    expect(tree.children[0]?.label).toBe('explore');
    expect(tree.children[0]?.sublabel).toBe('Explore');
  });

  it('nests an agent spawned by another agent', () => {
    const tree = buildSessionTree({
      ...base,
      lines: [assistant([{ type: 'tool_use', id: 'toolu_parent', name: 'Agent', input: { description: 'parent' } }])],
      subagents: [
        {
          agentId: 'aparent',
          meta: { description: 'parent', toolUseId: 'toolu_parent', spawnDepth: 1 },
          lines: [assistant([{ type: 'tool_use', id: 'toolu_child', name: 'Agent', input: { description: 'child' } }])],
        },
        {
          agentId: 'achild',
          meta: { description: 'child', toolUseId: 'toolu_child', spawnDepth: 2 },
          lines: [],
        },
      ],
    });

    expect(tree.children).toHaveLength(1);
    expect(tree.children[0]?.children).toHaveLength(1);
    expect(tree.children[0]?.children[0]?.label).toBe('child');
  });

  it('marks a subagent running until its tool call completes', () => {
    const spawn = assistant([{ type: 'tool_use', id: 'toolu_r', name: 'Agent', input: { description: 'busy' } }]);
    const running = buildSessionTree({
      ...base,
      lines: [spawn],
      subagents: [{ agentId: 'a1', meta: { toolUseId: 'toolu_r', spawnDepth: 1 }, lines: [] }],
    });
    expect(running.children[0]?.status).toBe('running');

    const finished = buildSessionTree({
      ...base,
      lines: [spawn, user([{ type: 'tool_result', tool_use_id: 'toolu_r', content: 'done' }])],
      subagents: [{ agentId: 'a1', meta: { toolUseId: 'toolu_r', spawnDepth: 1 }, lines: [] }],
    });
    expect(finished.children[0]?.status).toBe('done');
  });

  it('groups workflow agents under a run node and counts progress from the journal', () => {
    const tree = buildSessionTree({
      ...base,
      lines: [],
      subagents: [],
      workflows: [
        {
          runId: 'wf_abc',
          journal: [
            { type: 'started', agentId: 'a1' },
            { type: 'started', agentId: 'a2' },
            { type: 'result', agentId: 'a1' },
          ],
          agents: [
            { agentId: 'a1', meta: { agentType: 'workflow-subagent' }, lines: [] },
            { agentId: 'a2', meta: { agentType: 'workflow-subagent' }, lines: [] },
          ],
        },
      ],
    });

    const workflow = tree.children[0];
    expect(workflow?.kind).toBe('workflow');
    expect(workflow?.sublabel).toBe('1/2 done');
    expect(workflow?.status).toBe('running');
    expect(workflow?.children.map((child) => child.status)).toEqual(['done', 'running']);
  });

  it('treats a recently written transcript as live', () => {
    const live = buildSessionTree({ ...base, lines: [], subagents: [], nowMs: base.mtimeMs + 5_000 });
    expect(live.status).toBe('live');
    const stale = buildSessionTree({ ...base, lines: [], subagents: [], nowMs: base.mtimeMs + 600_000 });
    expect(stale.status).toBe('done');
  });
});

describe('deriveLabel', () => {
  function userLine(text: string): TranscriptLine {
    return { type: 'user', message: { role: 'user', content: [{ type: 'text', text }] as never } };
  }

  it('reads the indented task that follows the computed-task marker', () => {
    const label = deriveLabel([
      userLine('[Workflow harness — user request] The harness relays, verbatim and indented below…'),
      userLine(
        '[Workflow harness — computed task] The task text below was computed at runtime.\n\n  You are skeptic #3 on a verification panel.\n  More detail here.',
      ),
    ]);
    expect(label).toBe('skeptic #3 on a verification panel.');
  });

  it('ignores harness preamble and command wrappers when no computed task exists', () => {
    expect(deriveLabel([userLine('[Workflow harness — user request] blah'), userLine('<command-name>/fix</command-name>')])).toBeUndefined();
    expect(deriveLabel([userLine('Review the auth module')])).toBe('Review the auth module');
  });

  it('returns undefined when there is nothing to read', () => {
    expect(deriveLabel([])).toBeUndefined();
  });
});

describe('erroredToolUseIds', () => {
  it('collects only tool results flagged as errors', () => {
    const errored = erroredToolUseIds([
      user([{ type: 'tool_result', tool_use_id: 'ok', content: 'fine' }]),
      user([{ type: 'tool_result', tool_use_id: 'bad', content: 'boom', is_error: true }]),
    ]);
    expect([...errored]).toEqual(['bad']);
  });

  it('does not mark an agent failed just because one of its own tools errored', () => {
    const spawn = assistant([{ type: 'tool_use', id: 'toolu_s', name: 'Agent', input: { description: 'worker' } }]);
    const tree = buildSessionTree({
      sessionId: 'sess',
      mtimeMs: 0,
      nowMs: 10_000_000,
      liveWindowSeconds: 60,
      workflows: [],
      lines: [spawn, user([{ type: 'tool_result', tool_use_id: 'toolu_s', content: 'summary' }])],
      subagents: [
        {
          agentId: 'a1',
          meta: { toolUseId: 'toolu_s', spawnDepth: 1 },
          lines: [
            assistant([{ type: 'tool_use', id: 'inner', name: 'Grep', input: { pattern: 'x' } }]),
            user([{ type: 'tool_result', tool_use_id: 'inner', content: 'no match', is_error: true }]),
          ],
        },
      ],
    });
    expect(tree.children[0]?.status).toBe('done');
  });
});

describe('propagateActivity', () => {
  function node(id: string, status: NodeStatus, children: AgentNode[] = []): AgentNode {
    return { id, kind: 'agent', label: id, status, events: [], children };
  }

  it('carries a working leaf all the way up to the root', () => {
    const leaf = node('leaf', 'live');
    const mid = node('mid', 'done', [leaf]);
    const root = node('root', 'done', [mid]);

    propagateActivity(root);

    expect([root.status, mid.status, leaf.status]).toEqual(['live', 'live', 'live']);
  });

  it('leaves a branch alone when nothing under it is working', () => {
    const quiet = node('quiet', 'done', [node('a', 'done'), node('b', 'done')]);
    propagateActivity(quiet);
    expect(quiet.status).toBe('done');
  });

  it('prefers live over running when a parent has both kinds of child', () => {
    const root = node('root', 'done', [node('a', 'running'), node('b', 'live')]);
    propagateActivity(root);
    expect(root.status).toBe('live');
  });

  it('raises a done parent to running when its child is merely launched', () => {
    const root = node('root', 'done', [node('a', 'running')]);
    propagateActivity(root);
    expect(root.status).toBe('running');
  });

  it('keeps a failure visible rather than painting over it', () => {
    const failed = node('failed', 'error', [node('a', 'live')]);
    propagateActivity(failed);
    expect(failed.status).toBe('error');
  });

  it('still reports the activity under a failed node so the path above it stays green', () => {
    const root = node('root', 'done', [node('failed', 'error', [node('a', 'live')])]);
    propagateActivity(root);
    expect(root.status).toBe('live');
  });
});

describe('an agent blocked on a tool', () => {
  const stale = { liveWindowSeconds: 60, nowMs: 10_000_000, mtimeMs: 9_000_000 };

  function tree(lines: TranscriptLine[]) {
    return buildSessionTree({
      sessionId: 'abcdef12-0000-0000-0000-000000000000',
      lines,
      mtimeMs: stale.mtimeMs,
      subagents: [],
      workflows: [],
      liveWindowSeconds: stale.liveWindowSeconds,
      nowMs: stale.nowMs,
    });
  }

  const started = new Date(10_000_000 - 240_000).toISOString();

  it('reads as running, not finished, while a tool call has not come back', () => {
    const node = tree([
      { ...assistant([{ type: 'tool_use', id: 'toolu_1', name: 'Bash', input: { command: 'pytest -x' } }]), timestamp: started },
    ]);

    expect(node.status).toBe('running');
    expect(node.waiting).toBe('waiting on Bash · 4m');
  });

  it('goes quiet once the result lands', () => {
    const node = tree([
      assistant([{ type: 'tool_use', id: 'toolu_1', name: 'Bash', input: { command: 'pytest -x' } }]),
      user([{ type: 'tool_result', tool_use_id: 'toolu_1', content: 'ok' }]),
    ]);

    expect(node.status).toBe('done');
    expect(node.waiting).toBeUndefined();
  });

  it('is not waiting when the call came back an error', () => {
    const node = tree([
      assistant([{ type: 'tool_use', id: 'toolu_1', name: 'Bash', input: { command: 'pytest -x' } }]),
      user([{ type: 'tool_result', tool_use_id: 'toolu_1', content: 'boom', is_error: true }]),
    ]);

    expect(node.waiting).toBeUndefined();
  });

  it('is not waiting once you have interrupted and said something else', () => {
    const node = tree([
      assistant([{ type: 'tool_use', id: 'toolu_1', name: 'Bash', input: { command: 'sleep 999' } }]),
      user([{ type: 'text', text: 'stop, do something else' }]),
    ]);

    expect(node.status).toBe('done');
    expect(node.waiting).toBeUndefined();
  });

  it('reports the last of several parallel calls still outstanding', () => {
    const events = buildEvents([
      assistant([
        { type: 'tool_use', id: 'toolu_1', name: 'Read', input: { file_path: '/a' } },
        { type: 'tool_use', id: 'toolu_2', name: 'Bash', input: { command: 'make test' } },
      ]),
      user([{ type: 'tool_result', tool_use_id: 'toolu_1', content: 'contents' }]),
    ]);

    expect(waitingOn(events)?.name).toBe('Bash');
  });

  it('carries a blocked grandchild up through parents that are not themselves waiting', () => {
    const node = buildSessionTree({
      sessionId: 'abcdef12-0000-0000-0000-000000000000',
      lines: [
        assistant([{ type: 'tool_use', id: 'toolu_parent', name: 'Agent', input: { description: 'parent' } }]),
        user([{ type: 'tool_result', tool_use_id: 'toolu_parent', content: 'launched' }]),
      ],
      mtimeMs: stale.mtimeMs,
      subagents: [
        {
          agentId: 'aparent',
          meta: { description: 'parent', toolUseId: 'toolu_parent', spawnDepth: 1 },
          mtimeMs: stale.mtimeMs,
          lines: [
            assistant([{ type: 'tool_use', id: 'toolu_child', name: 'Agent', input: { description: 'child' } }]),
            user([{ type: 'tool_result', tool_use_id: 'toolu_child', content: 'launched' }]),
          ],
        },
        {
          agentId: 'achild',
          meta: { description: 'child', toolUseId: 'toolu_child', spawnDepth: 2 },
          mtimeMs: stale.mtimeMs,
          lines: [
            {
              ...assistant([{ type: 'tool_use', id: 'toolu_deep', name: 'Bash', input: { command: 'terraform apply' } }]),
              timestamp: started,
            },
          ],
        },
      ],
      workflows: [],
      liveWindowSeconds: stale.liveWindowSeconds,
      nowMs: stale.nowMs,
    });

    const parent = node.children[0];
    const child = parent?.children[0];

    expect(child?.label).toBe('child');
    expect(child?.status).toBe('running');
    expect(child?.waiting).toBe('waiting on Bash · 4m');

    expect(parent?.waiting).toBeUndefined();
    expect(parent?.status).toBe('running');
    expect(node.waiting).toBeUndefined();
    expect(node.status).toBe('running');
  });

  it('leaves a live node green rather than demoting it to waiting', () => {
    const node = buildSessionTree({
      sessionId: 'abcdef12-0000-0000-0000-000000000000',
      lines: [assistant([{ type: 'tool_use', id: 'toolu_1', name: 'Bash', input: { command: 'x' } }])],
      mtimeMs: 10_000_000,
      subagents: [],
      workflows: [],
      liveWindowSeconds: 60,
      nowMs: 10_000_000,
    });

    expect(node.status).toBe('live');
  });
});
