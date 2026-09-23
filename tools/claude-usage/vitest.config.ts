import * as path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      vscode: path.resolve(import.meta.dirname, 'src/testing/vscodeStub.ts'),
    },
  },
  test: {
    include: ['src/**/*.test.ts'],
  },
});
