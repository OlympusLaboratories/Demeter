import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { activate } from './extension';
import {
  makeGroup,
  makeTab,
  makeTerminal,
  onDidChangeActiveTerminal,
  onDidChangeTabs,
  resetState,
  state,
  type StubGroup,
  type StubTab,
  type StubTerminal,
} from './testing/vscodeStub';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const settle = () => sleep(320);

let root: string;
let repo: string;
const worktree = (name: string) => path.join(repo, '.claude', 'worktrees', 'dylan', name);

const aiTitle = (title: string, sessionId: string) =>
  JSON.stringify({ type: 'ai-title', aiTitle: title, sessionId });
const message = (cwd: string, sessionId: string) =>
  JSON.stringify({ type: 'user', cwd, sessionId });
const customTitle = (title: string, sessionId: string) =>
  JSON.stringify({ type: 'custom-title', customTitle: title, sessionId });
const worktreeState = (worktreePath: string, sessionId: string) =>
  JSON.stringify({
    type: 'worktree-state',
    worktreeSession: { worktreePath, worktreeName: path.basename(worktreePath) },
    sessionId,
  });

async function writeSession(
  dir: string,
  sessionId: string,
  lines: string[],
  mtime?: Date,
): Promise<void> {
  const target = path.join(root, 'projects', dir);
  await fs.mkdir(target, { recursive: true });
  const file = path.join(target, `${sessionId}.jsonl`);
  await fs.writeFile(file, lines.join('\n'), 'utf8');
  if (mtime) {
    await fs.utimes(file, mtime, mtime);
  }
}

beforeAll(async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), 'worktree-sync-'));
  repo = path.join(root, 'gridmatic-dev');

  await writeSession('wt-2401', 's2401', [
    message(repo, 's2401'),
    worktreeState(worktree('PLAT-2401'), 's2401'),
    aiTitle('PLAT-2401', 's2401'),
  ]);
  await writeSession('wt-2405', 's2405', [
    worktreeState(worktree('PLAT-2405'), 's2405'),
    aiTitle('PLAT-2405', 's2405'),
  ]);
  await writeSession('wt-2406', 's2406', [
    worktreeState(worktree('PLAT-2406'), 's2406'),
    aiTitle('PLAT-2406 fix', 's2406'),
  ]);
  await writeSession('wt-2407', 's2407', [
    worktreeState(worktree('PLAT-2407'), 's2407'),
    customTitle('PLAT-2407', 's2407'),
  ]);
  // A worktree session whose generated title is wrong, so it is only findable by
  // its worktree name; an older repo-root session already claims that name as a
  // title; and the rename itself lands in a stub with no location at all.
  await writeSession(
    'wt-2472',
    's2472',
    [
      worktreeState(worktree('PLAT-2472'), 's2472'),
      aiTitle('Monitor MR 761 merge then run fix-linear on PLAT-2472', 's2472'),
    ],
    new Date('2026-09-02T19:42:00Z'),
  );
  await writeSession(
    'repo-2472',
    's2472root',
    [aiTitle('PLAT-2472', 's2472root'), message(repo, 's2472root')],
    new Date('2026-09-02T18:50:00Z'),
  );
  await writeSession('repo-stub', 's2472stub', [customTitle('PLAT-2472', 's2472stub')]);

  await writeSession('repo-a', 's2408', [aiTitle('PLAT-2408', 's2408'), message(repo, 's2408')]);
  await writeSession('repo-b', 'schat', [
    aiTitle('Chat context check', 'schat'),
    message(repo, 'schat'),
  ]);
});

afterAll(async () => {
  await fs.rm(root, { recursive: true, force: true });
});

interface Fixture {
  group: StubGroup;
  tabNew: StubTab;
  tab2401: StubTab;
  tab2405: StubTab;
  tab2406: StubTab;
  tab2407: StubTab;
  tab2408: StubTab;
  tabChat: StubTab;
  t2401: StubTerminal;
  t2405: StubTerminal;
  t2406: StubTerminal;
  t2407: StubTerminal;
  t2401Nested: StubTerminal;
  tRepo: StubTerminal;
}

let f: Fixture;

function activateTab(tab: StubTab): void {
  for (const candidate of f.group.tabs) {
    candidate.isActive = false;
  }
  tab.isActive = true;
  f.group.activeTab = tab;
}

beforeEach(async () => {
  resetState();
  state.config.projectsDir = path.join(root, 'projects');

  const group = makeGroup(1);
  const tabNew = makeTab('Claude Code', group);
  const tab2401 = makeTab('PLAT-2401', group);
  const tab2405 = makeTab('PLAT-2405', group);
  const tab2406 = makeTab('PLAT-2406', group);
  const tab2407 = makeTab('PLAT-2407', group);
  const tab2408 = makeTab('PLAT-2408', group);
  const tabChat = makeTab('Chat context check', group);
  group.tabs = [tabNew, tab2401, tab2405, tab2406, tab2407, tab2408, tabChat];
  state.tabGroups = [group];

  const t2401 = makeTerminal('zsh 2401', worktree('PLAT-2401'));
  const t2405 = makeTerminal('zsh 2405', worktree('PLAT-2405'));
  const t2406 = makeTerminal('zsh 2406', worktree('PLAT-2406'));
  const t2407 = makeTerminal('zsh 2407', worktree('PLAT-2407'));
  const t2401Nested = makeTerminal('zsh nested', path.join(worktree('PLAT-2401'), 'apps/iam'));
  const tRepo = makeTerminal('zsh repo', repo);
  state.terminals = [t2401, t2405, t2406, t2407, t2401Nested, tRepo];

  f = {
    group,
    tabNew,
    tab2401,
    tab2405,
    tab2406,
    tab2407,
    tab2408,
    tabChat,
    t2401,
    t2405,
    t2406,
    t2407,
    t2401Nested,
    tRepo,
  };

  activate({ subscriptions: [] } as never);
  await settle();
  state.showCalls = [];
  state.commandCalls = [];
});

describe('activation', () => {
  it('registers its commands and builds the index', () => {
    expect([...state.registered.keys()].sort()).toEqual([
      'worktreeSync.diagnostics',
      'worktreeSync.rebuildIndex',
      'worktreeSync.toggle',
    ]);
    expect(state.logLines.some((line) => line.includes('indexed'))).toBe(true);
  });
});

describe('Claude tab to terminal', () => {
  it('reveals the matching terminal without stealing focus', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual(['zsh 2401:preserveFocus=true']);
  });

  it('follows a switch to another tab', async () => {
    activateTab(f.tab2405);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual(['zsh 2405:preserveFocus=true']);
  });

  it('matches a tab named after its worktree when the ai title differs', async () => {
    activateTab(f.tab2406);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual(['zsh 2406:preserveFocus=true']);
  });

  it('matches a manually renamed tab that has only a custom-title', async () => {
    activateTab(f.tab2407);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual(['zsh 2407:preserveFocus=true']);
  });

  it('prefers the worktree over a repo-root session that claims the same name', async () => {
    const tab2472 = makeTab('PLAT-2472', f.group);
    f.group.tabs = [...f.group.tabs, tab2472];
    const t2472 = makeTerminal('zsh 2472', worktree('PLAT-2472'));
    state.terminals = [...state.terminals, t2472];

    activateTab(tab2472);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual(['zsh 2472:preserveFocus=true']);
  });

  it('does nothing for a tab with no session on disk', async () => {
    activateTab(f.tabNew);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual([]);
    expect(state.logLines.some((l) => l.includes('"Claude Code"') && l.includes('no worktree'))).toBe(true);
  });

  it('does nothing when no terminal is open for the worktree', async () => {
    state.terminals = [f.tRepo];
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual([]);
    expect(state.logLines.some((l) => l.includes('no terminal open'))).toBe(true);
  });
});

describe('terminal to Claude tab', () => {
  it('activates the matching tab and hands focus back', async () => {
    activateTab(f.tabNew);
    state.activeTerminal = f.t2401;
    onDidChangeActiveTerminal.fire(f.t2401);
    await settle();
    expect(state.commandCalls).toEqual([
      'workbench.action.focusFirstEditorGroup',
      `workbench.action.openEditorAtIndex(${f.group.tabs.indexOf(f.tab2401)})`,
      'workbench.action.terminal.focus',
    ]);
  });

  it('maps a subdirectory to its enclosing worktree, not the repo root', async () => {
    activateTab(f.tabNew);
    state.activeTerminal = f.t2401Nested;
    onDidChangeActiveTerminal.fire(f.t2401Nested);
    await settle();
    expect(state.commandCalls).toContain(
      `workbench.action.openEditorAtIndex(${f.group.tabs.indexOf(f.tab2401)})`,
    );
  });

  it('finds the worktree-named tab whose ai title differs', async () => {
    activateTab(f.tabNew);
    state.activeTerminal = f.t2406;
    onDidChangeActiveTerminal.fire(f.t2406);
    await settle();
    expect(state.commandCalls).toContain(
      `workbench.action.openEditorAtIndex(${f.group.tabs.indexOf(f.tab2406)})`,
    );
  });

  it('finds the manually renamed tab', async () => {
    activateTab(f.tabNew);
    state.activeTerminal = f.t2407;
    onDidChangeActiveTerminal.fire(f.t2407);
    await settle();
    expect(state.commandCalls).toContain(
      `workbench.action.openEditorAtIndex(${f.group.tabs.indexOf(f.tab2407)})`,
    );
  });

  it('skips rather than guessing when several tabs share a worktree', async () => {
    activateTab(f.tabNew);
    state.activeTerminal = f.tRepo;
    onDidChangeActiveTerminal.fire(f.tRepo);
    await settle();
    expect(state.commandCalls).toEqual([]);
    expect(state.logLines.some((line) => line.includes('ambiguous'))).toBe(true);
  });

  it('stays put when a matching tab is already active', async () => {
    activateTab(f.tab2408);
    state.activeTerminal = f.tRepo;
    onDidChangeActiveTerminal.fire(f.tRepo);
    await settle();
    expect(state.commandCalls).toEqual([]);
  });
});

describe('background session activity', () => {
  it('does not move the terminal when a background tab gains a dot', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await settle();
    state.showCalls = [];

    // A background session finishes: VS Code re-reconciles the group, which
    // transiently leaves it with no active tab, then restores it.
    f.group.activeTab = undefined;
    onDidChangeTabs.fire({});
    f.group.activeTab = f.tab2401;
    onDidChangeTabs.fire({});
    await settle();

    expect(state.showCalls).toEqual([]);
  });

  it('ignores a background editor group whose active tab changes', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await settle();
    state.showCalls = [];

    // A second group the user is not looking at; its Claude session finishes and
    // VS Code re-marks that tab active inside its own group.
    const background = makeGroup(2);
    const tab2406bg = makeTab('PLAT-2406', background);
    background.tabs = [tab2406bg];
    background.activeTab = undefined;
    state.tabGroups = [f.group, background];
    state.activeGroupIndex = 0;
    onDidChangeTabs.fire({});

    background.activeTab = tab2406bg;
    onDidChangeTabs.fire({});
    await settle();

    expect(state.showCalls).toEqual([]);
  });

  it('does follow a switch the user makes inside a second group', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await settle();
    state.showCalls = [];

    const second = makeGroup(2);
    const tab2406b = makeTab('PLAT-2406', second);
    second.tabs = [tab2406b];
    second.activeTab = tab2406b;
    tab2406b.isActive = true;
    state.tabGroups = [f.group, second];
    state.activeGroupIndex = 1;
    onDidChangeTabs.fire({});
    await settle();

    expect(state.showCalls).toEqual(['zsh 2406:preserveFocus=true']);
  });

  it('does not re-sync when the active tab only regenerates its title', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await settle();
    state.showCalls = [];

    onDidChangeTabs.fire({});
    onDidChangeTabs.fire({});
    await settle();

    expect(state.showCalls).toEqual([]);
  });

  it('still follows a real switch made right after background churn', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await settle();
    state.showCalls = [];

    f.group.activeTab = undefined;
    onDidChangeTabs.fire({});
    f.group.activeTab = f.tab2401;
    onDidChangeTabs.fire({});
    await settle();

    activateTab(f.tab2405);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual(['zsh 2405:preserveFocus=true']);
  });
});

describe('loop safety', () => {
  it('does nothing when both sides already agree', async () => {
    activateTab(f.tab2401);
    state.activeTerminal = f.t2401;
    onDidChangeActiveTerminal.fire(f.t2401);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.commandCalls).toEqual([]);
    expect(state.showCalls).toEqual([]);
  });

  it('does not lose a tab switch that lands while a previous sync is settling', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await sleep(40);
    expect(state.showCalls).toEqual(['zsh 2401:preserveFocus=true']);

    activateTab(f.tab2405);
    onDidChangeTabs.fire({});
    await sleep(700);
    expect(state.showCalls).toContain('zsh 2405:preserveFocus=true');
  });

  it('does not lose a tab switch that lands while background tabs are churning', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await sleep(40);

    activateTab(f.tab2406);
    onDidChangeTabs.fire({});
    onDidChangeTabs.fire({});
    onDidChangeTabs.fire({});
    await sleep(700);
    expect(state.showCalls).toContain('zsh 2406:preserveFocus=true');
  });

  it('settles after a tab switch instead of ping-ponging', async () => {
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await sleep(600);
    expect(state.showCalls).toEqual(['zsh 2401:preserveFocus=true']);
    expect(state.commandCalls).toEqual([]);
  });
});

describe('settings', () => {
  it('tabToTerminal suppresses the terminal-driven direction', async () => {
    state.config.direction = 'tabToTerminal';
    activateTab(f.tabNew);
    state.activeTerminal = f.t2401;
    onDidChangeActiveTerminal.fire(f.t2401);
    await settle();
    expect(state.commandCalls).toEqual([]);
  });

  it('terminalToTab suppresses the tab-driven direction', async () => {
    state.config.direction = 'terminalToTab';
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    await settle();
    expect(state.showCalls).toEqual([]);
  });

  it('disabled means inert in both directions', async () => {
    state.config.enabled = false;
    activateTab(f.tab2401);
    onDidChangeTabs.fire({});
    onDidChangeActiveTerminal.fire(f.t2405);
    await settle();
    expect(state.showCalls).toEqual([]);
    expect(state.commandCalls).toEqual([]);
  });
});

describe('diagnostics', () => {
  it('explains what resolved, what did not, and what is ambiguous', async () => {
    state.logLines = [];
    await state.registered.get('worktreeSync.diagnostics')?.();
    const report = state.logLines.join('\n');

    expect(report).toContain('--- Claude tabs ---');
    expect(report).toContain(worktree('PLAT-2401'));
    expect(report).toContain('UNRESOLVED (no session on disk with this title or worktree name)');
    expect(report).toContain('--- Ambiguous');
    expect(report).toContain('"PLAT-2408"');
    expect(report).toContain('cwd=');
  });

  it('reports a terminal with no shell integration rather than crashing', async () => {
    state.terminals = [makeTerminal('bare zsh', undefined)];
    state.logLines = [];
    await state.registered.get('worktreeSync.diagnostics')?.();
    expect(state.logLines.join('\n')).toContain('NO CWD (shell integration not ready)');
  });
});
