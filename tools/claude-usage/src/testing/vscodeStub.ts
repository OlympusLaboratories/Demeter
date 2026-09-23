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

export const StatusBarAlignment = { Left: 1, Right: 2 } as const;
export const ProgressLocation = { Notification: 15 } as const;
export const ConfigurationTarget = { Global: 1, Workspace: 2 } as const;

export class ThemeColor {
  constructor(public readonly id: string) {}
}

export class MarkdownString {
  value = '';
  isTrusted = false;
  supportThemeIcons = false;
  appendMarkdown(text: string): this {
    this.value += text;
    return this;
  }
}

export const Uri = {
  parse: (value: string) => ({ toString: () => value }),
};

export interface StubStatusBarItem {
  alignment: number;
  priority: number;
  text: string;
  tooltip: unknown;
  color: unknown;
  command: unknown;
  visible: boolean;
  disposed: boolean;
  show(): void;
  hide(): void;
  dispose(): void;
}

export const state = {
  config: {} as Record<string, unknown>,
  statusItems: [] as StubStatusBarItem[],
  commands: new Map<string, (...args: unknown[]) => unknown>(),
  logLines: [] as string[],
  infoMessages: [] as string[],
  warningMessages: [] as string[],
  openedExternal: [] as string[],
  focused: true,
};

export const onDidChangeWindowState = stubEvent<{ focused: boolean }>();
export const onDidChangeConfiguration = stubEvent<{ affectsConfiguration(section: string): boolean }>();

export const window = {
  createOutputChannel: () => ({
    appendLine: (line: string) => state.logLines.push(line),
    show() {},
    dispose() {},
  }),
  createStatusBarItem: (alignment: number, priority: number): StubStatusBarItem => {
    const item: StubStatusBarItem = {
      alignment,
      priority,
      text: '',
      tooltip: undefined,
      color: undefined,
      command: undefined,
      visible: false,
      disposed: false,
      show() {
        item.visible = true;
      },
      hide() {
        item.visible = false;
      },
      dispose() {
        item.visible = false;
        item.disposed = true;
      },
    };
    state.statusItems.push(item);
    return item;
  },
  showInformationMessage: (message: string) => {
    state.infoMessages.push(message);
    return Promise.resolve(undefined);
  },
  showWarningMessage: (message: string) => {
    state.warningMessages.push(message);
    return Promise.resolve(undefined);
  },
  showErrorMessage: () => Promise.resolve(undefined),
  showInputBox: () => Promise.resolve(undefined),
  createQuickPick: () => ({
    title: '',
    placeholder: '',
    items: [] as unknown[],
    activeItems: [] as unknown[],
    onDidChangeActive: () => ({ dispose() {} }),
    onDidAccept: () => ({ dispose() {} }),
    onDidHide: () => ({ dispose() {} }),
    show() {},
    hide() {},
    dispose() {},
  }),
  withProgress: (_options: unknown, task: (progress: unknown, token: unknown) => unknown) =>
    task({ report() {} }, { onCancellationRequested() {} }),
  get state() {
    return { focused: state.focused };
  },
  onDidChangeWindowState,
};

export const workspace = {
  getConfiguration: () => ({
    get: (key: string, fallback: unknown) => (key in state.config ? state.config[key] : fallback),
    update: (key: string, value: unknown) => {
      state.config[key] = value;
      return Promise.resolve();
    },
  }),
  onDidChangeConfiguration,
};

export const commands = {
  registerCommand: (id: string, handler: (...args: unknown[]) => unknown) => {
    state.commands.set(id, handler);
    return { dispose() {} };
  },
};

export const env = {
  openExternal: (uri: { toString(): string }) => {
    state.openedExternal.push(uri.toString());
    return Promise.resolve(true);
  },
};

export function visibleItems(): StubStatusBarItem[] {
  return state.statusItems.filter((item) => item.visible && !item.disposed);
}

export function resetState(): void {
  for (const event of allEvents) {
    event.clear();
  }
  state.config = {};
  state.statusItems = [];
  state.commands = new Map();
  state.logLines = [];
  state.infoMessages = [];
  state.warningMessages = [];
  state.openedExternal = [];
  state.focused = true;
}
