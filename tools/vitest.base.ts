import * as path from 'node:path';

export function vitestConfig(dir: string, env?: Record<string, string>) {
  return {
    resolve: {
      alias: {
        vscode: path.resolve(dir, 'src/testing/vscodeStub.ts'),
      },
    },
    test: {
      include: ['src/**/*.test.ts'],
      ...(env ? { env } : {}),
    },
  };
}
