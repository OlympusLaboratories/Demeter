import { execFile } from 'node:child_process';
import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { promisify } from 'node:util';

const run = promisify(execFile);

export const KEYCHAIN_SERVICE = 'Claude Code-credentials';

export interface ClaudeCodeToken {
  accessToken: string;
  expiresAt?: number;
}

export function credentialsFilePath(): string {
  return path.join(os.homedir(), '.claude', '.credentials.json');
}

export function parseCredentials(text: string): ClaudeCodeToken | undefined {
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return undefined;
  }
  if (typeof body !== 'object' || body === null) {
    return undefined;
  }
  const oauth = (body as Record<string, unknown>)['claudeAiOauth'];
  if (typeof oauth !== 'object' || oauth === null) {
    return undefined;
  }
  const record = oauth as Record<string, unknown>;
  const accessToken = record['accessToken'];
  if (typeof accessToken !== 'string' || accessToken.length === 0) {
    return undefined;
  }
  const expiresAt = record['expiresAt'];
  return {
    accessToken,
    expiresAt: typeof expiresAt === 'number' && Number.isFinite(expiresAt) ? expiresAt : undefined,
  };
}

export function isUsable(token: ClaudeCodeToken | undefined, now: number, skewMs = 60_000): boolean {
  if (token === undefined) {
    return false;
  }
  return token.expiresAt === undefined || token.expiresAt - skewMs > now;
}

async function readKeychain(): Promise<string | undefined> {
  const attempts = [
    ['find-generic-password', '-s', KEYCHAIN_SERVICE, '-a', os.userInfo().username, '-w'],
    ['find-generic-password', '-s', KEYCHAIN_SERVICE, '-w'],
  ];
  for (const args of attempts) {
    try {
      const { stdout } = await run('security', args, { timeout: 10_000, maxBuffer: 1024 * 1024 });
      const trimmed = stdout.trim();
      if (trimmed.length > 0) {
        return trimmed;
      }
    } catch {
      continue;
    }
  }
  return undefined;
}

async function readFileStore(): Promise<string | undefined> {
  try {
    return await fs.readFile(credentialsFilePath(), 'utf8');
  } catch {
    return undefined;
  }
}

export async function readClaudeCodeToken(platform: NodeJS.Platform = process.platform): Promise<ClaudeCodeToken | undefined> {
  const fromEnv = process.env['CLAUDE_CODE_OAUTH_TOKEN'];
  if (typeof fromEnv === 'string' && fromEnv.length > 0) {
    return { accessToken: fromEnv };
  }
  const sources = platform === 'darwin' ? [readKeychain, readFileStore] : [readFileStore, readKeychain];
  for (const source of sources) {
    const text = await source();
    if (text === undefined) {
      continue;
    }
    const token = parseCredentials(text);
    if (token) {
      return token;
    }
  }
  return undefined;
}
