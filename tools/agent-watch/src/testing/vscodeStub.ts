type Listener<T> = (arg: T) => void;

export interface StubEvent<T> {
  (listener: Listener<T>): { dispose(): void };
  fire(arg: T): void;
  clear(): void;
}

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
  return event;
}

export const ViewColumn = { Active: -1, Beside: -2, One: 1 } as const;
export const StatusBarAlignment = { Left: 1, Right: 2 } as const;

export class Uri {
  private constructor(public readonly fsPath: string) {}
  static file(value: string): Uri {
    return new Uri(value);
  }
  static joinPath(base: Uri, ...segments: string[]): Uri {
    return new Uri([base.fsPath, ...segments].join('/'));
  }
  toString(): string {
    return this.fsPath;
  }
}

export const configValues = new Map<string, unknown>();

export const workspace = {
  workspaceFolders: undefined as { uri: Uri }[] | undefined,
  onDidChangeConfiguration: stubEvent<{ affectsConfiguration(section: string): boolean }>(),
  getConfiguration(section: string) {
    return {
      get<T>(key: string): T | undefined {
        return configValues.get(`${section}.${key}`) as T | undefined;
      },
    };
  },
};

export const registeredCommands = new Map<string, (...args: unknown[]) => unknown>();

export const commands = {
  registerCommand(command: string, handler: (...args: unknown[]) => unknown) {
    registeredCommands.set(command, handler);
    return { dispose: () => registeredCommands.delete(command) };
  },
  executeCommand: async () => undefined,
  getCommands: async () => [...registeredCommands.keys()],
};

export const createdPanels: StubPanel[] = [];

export interface StubStatusBarItem {
  alignment: number | undefined;
  priority: number | undefined;
  text: string;
  tooltip: string | undefined;
  command: string | undefined;
  shown: boolean;
  show(): void;
  hide(): void;
  dispose(): void;
}

export const statusBarItems: StubStatusBarItem[] = [];

export interface StubPanel {
  visible: boolean;
  viewColumn: number | undefined;
  onDidChangeViewState: StubEvent<void>;
  reveal(column?: number, preserveFocus?: boolean): void;
  revealCalls: { column?: number; preserveFocus?: boolean }[];
  webview: {
    html: string;
    options: Record<string, unknown>;
    cspSource: string;
    asWebviewUri(uri: Uri): Uri;
    postMessage(message: unknown): Promise<boolean>;
    onDidReceiveMessage: StubEvent<unknown>;
    posted: unknown[];
  };
  dispose(): void;
  onDidDispose: StubEvent<void>;
}

export const registeredSerializers = new Map<string, unknown>();

export const window = {
  createStatusBarItem(alignment?: number, priority?: number): StubStatusBarItem {
    const item: StubStatusBarItem = {
      alignment,
      priority,
      text: '',
      tooltip: undefined,
      command: undefined,
      shown: false,
      show() {
        this.shown = true;
      },
      hide() {
        this.shown = false;
      },
      dispose() {
        this.shown = false;
      },
    };
    statusBarItems.push(item);
    return item;
  },
  registerWebviewPanelSerializer(viewType: string, serializer: unknown) {
    registeredSerializers.set(viewType, serializer);
    return { dispose: () => registeredSerializers.delete(viewType) };
  },
  createWebviewPanel(): StubPanel {
    const posted: unknown[] = [];
    const revealCalls: { column?: number; preserveFocus?: boolean }[] = [];
    const panel: StubPanel = {
      visible: true,
      viewColumn: 1,
      onDidChangeViewState: stubEvent<void>(),
      revealCalls,
      reveal: (column?: number, preserveFocus?: boolean) => {
        revealCalls.push({ column, preserveFocus });
      },
      webview: {
        html: '',
        options: {} as Record<string, unknown>,
        cspSource: 'vscode-resource:',
        asWebviewUri: (uri: Uri) => uri,
        postMessage: async (message: unknown) => {
          posted.push(message);
          return true;
        },
        onDidReceiveMessage: stubEvent<unknown>(),
        posted,
      },
      dispose: () => undefined,
      onDidDispose: stubEvent<void>(),
    };
    createdPanels.push(panel);
    return panel;
  },
  showErrorMessage: async () => undefined,
  showWarningMessage: async () => undefined,
  showInformationMessage: async () => undefined,
};

export const extensions = {
  getExtension: () => undefined,
  all: [] as unknown[],
};

export function resetStub(): void {
  configValues.clear();
  registeredCommands.clear();
  registeredSerializers.clear();
  createdPanels.length = 0;
  statusBarItems.length = 0;
  workspace.workspaceFolders = undefined;
}
