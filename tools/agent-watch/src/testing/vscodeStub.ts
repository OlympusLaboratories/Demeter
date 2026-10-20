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

export interface StubPanel {
  webview: {
    html: string;
    cspSource: string;
    asWebviewUri(uri: Uri): Uri;
    postMessage(message: unknown): Promise<boolean>;
    onDidReceiveMessage: StubEvent<unknown>;
    posted: unknown[];
  };
  reveal(): void;
  dispose(): void;
  onDidDispose: StubEvent<void>;
}

export const window = {
  createWebviewPanel(): StubPanel {
    const posted: unknown[] = [];
    const panel: StubPanel = {
      webview: {
        html: '',
        cspSource: 'vscode-resource:',
        asWebviewUri: (uri: Uri) => uri,
        postMessage: async (message: unknown) => {
          posted.push(message);
          return true;
        },
        onDidReceiveMessage: stubEvent<unknown>(),
        posted,
      },
      reveal: () => undefined,
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
  createdPanels.length = 0;
  workspace.workspaceFolders = undefined;
}
