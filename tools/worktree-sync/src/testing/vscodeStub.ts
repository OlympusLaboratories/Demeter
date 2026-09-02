type Listener<T> = (arg: T) => void;

export interface StubEvent<T> {
  (listener: Listener<T>): { dispose(): void };
  fire(arg: T): void;
  clear(): void;
}

const allEvents: StubEvent<never>[] = [];

function stubEvent<T>(): StubEvent<T> {
  let listeners: Listener<T>[] = [];
  const event = ((listener: Listener<T>) => {
    listeners.push(listener);
    return {
      dispose() {
        listeners = listeners.filter((candidate) => candidate !== listener);
      },
    };
  }) as StubEvent<T>;
  event.fire = (arg: T) => [...listeners].forEach((listener) => listener(arg));
  event.clear = () => {
    listeners = [];
  };
  allEvents.push(event as unknown as StubEvent<never>);
  return event;
}

export class TabInputWebview {
  constructor(public readonly viewType: string) {}
}

export interface StubTerminal {
  name: string;
  creationOptions: { cwd?: string };
  shellIntegration?: { cwd?: { fsPath: string } };
  show(preserveFocus?: boolean): void;
}

export interface StubGroup {
  viewColumn: number;
  tabs: StubTab[];
  activeTab?: StubTab;
}

export interface StubTab {
  label: string;
  isActive: boolean;
  input: TabInputWebview;
  group: StubGroup;
}

export const state = {
  tabGroups: [] as StubGroup[],
  activeGroupIndex: 0,
  terminals: [] as StubTerminal[],
  activeTerminal: undefined as StubTerminal | undefined,
  commandCalls: [] as string[],
  showCalls: [] as string[],
  infoMessages: [] as string[],
  registered: new Map<string, (...args: unknown[]) => unknown>(),
  logLines: [] as string[],
  config: {
    enabled: true,
    direction: 'both',
    projectsDir: '~/.claude/projects',
    debounceMs: 0,
  } as Record<string, unknown>,
};

export const onDidChangeTabs = stubEvent<unknown>();
export const onDidChangeTabGroups = stubEvent<unknown>();
export const onDidChangeActiveTerminal = stubEvent<StubTerminal | undefined>();
export const onDidChangeTerminalShellIntegration = stubEvent<{ terminal: StubTerminal }>();
export const onDidCloseTerminal = stubEvent<StubTerminal>();

export const ConfigurationTarget = { Global: 1 } as const;

export const window = {
  createOutputChannel: () => ({
    appendLine: (line: string) => state.logLines.push(line),
    show: () => {},
    dispose: () => {},
  }),
  showInformationMessage: (message: string) => {
    state.infoMessages.push(message);
    return Promise.resolve(undefined);
  },
  get terminals() {
    return state.terminals;
  },
  get activeTerminal() {
    return state.activeTerminal;
  },
  tabGroups: {
    get all() {
      return state.tabGroups;
    },
    get activeTabGroup() {
      return state.tabGroups[state.activeGroupIndex];
    },
    onDidChangeTabs,
    onDidChangeTabGroups,
  },
  onDidChangeActiveTerminal,
  onDidChangeTerminalShellIntegration,
  onDidCloseTerminal,
};

export const workspace = {
  getConfiguration: () => ({
    get: (key: string, fallback: unknown) => (key in state.config ? state.config[key] : fallback),
    update: (key: string, value: unknown) => {
      state.config[key] = value;
      return Promise.resolve();
    },
  }),
};

export const commands = {
  registerCommand: (id: string, handler: (...args: unknown[]) => unknown) => {
    state.registered.set(id, handler);
    return { dispose() {} };
  },
  executeCommand: (id: string, ...args: unknown[]) => {
    state.commandCalls.push(args.length > 0 ? `${id}(${args.join(',')})` : id);
    return Promise.resolve(undefined);
  },
};

export function makeTerminal(name: string, cwd?: string): StubTerminal {
  const terminal: StubTerminal = {
    name,
    creationOptions: {},
    shellIntegration: cwd ? { cwd: { fsPath: cwd } } : undefined,
    show(preserveFocus?: boolean) {
      state.showCalls.push(`${name}:preserveFocus=${preserveFocus}`);
      state.activeTerminal = terminal;
    },
  };
  return terminal;
}

export function makeGroup(viewColumn: number): StubGroup {
  return { viewColumn, tabs: [], activeTab: undefined };
}

export function makeTab(label: string, group: StubGroup): StubTab {
  return {
    label,
    isActive: false,
    input: new TabInputWebview('mainThreadWebview-claudeVSCodePanel'),
    group,
  };
}

export function resetState(): void {
  for (const event of allEvents) {
    event.clear();
  }
  state.tabGroups = [];
  state.activeGroupIndex = 0;
  state.terminals = [];
  state.activeTerminal = undefined;
  state.commandCalls = [];
  state.showCalls = [];
  state.infoMessages = [];
  state.registered = new Map();
  state.logLines = [];
  state.config = {
    enabled: true,
    direction: 'both',
    projectsDir: '~/.claude/projects',
    debounceMs: 0,
  };
}
