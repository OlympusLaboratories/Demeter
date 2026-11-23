import * as os from 'node:os';
import * as path from 'node:path';
import { defineConfig } from 'vitest/config';
import { vitestConfig } from '../vitest.base';

export default defineConfig(vitestConfig(import.meta.dirname, {
  WORKTREE_SYNC_LOG_FILE: path.join(os.tmpdir(), `worktree-sync-test-${process.pid}.log`),
}));
