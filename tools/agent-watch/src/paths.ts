import * as os from 'node:os';
import * as path from 'node:path';

export function expandHome(input: string): string {
  if (input === '~') return os.homedir();
  if (input.startsWith('~/')) return path.join(os.homedir(), input.slice(2));
  return input;
}

export function claudeProjectsDir(override?: string): string {
  const explicit = override?.trim();
  if (explicit) return expandHome(explicit);
  const configDir = process.env.CLAUDE_CONFIG_DIR?.trim();
  if (configDir) return path.join(expandHome(configDir), 'projects');
  return path.join(os.homedir(), '.claude', 'projects');
}

export function slugForPath(dir: string): string {
  return dir.replace(/[/.]/g, '-');
}
