import * as crypto from 'node:crypto';
import * as http from 'node:http';
import { AddressInfo } from 'node:net';

export const CLIENT_ID = '9d1c250a-e61b-44d9-88ed-5944d1962f5e';
export const AUTHORIZE_URL = 'https://claude.com/cai/oauth/authorize';
export const TOKEN_URL = 'https://platform.claude.com/v1/oauth/token';
export const MANUAL_REDIRECT_URL = 'https://platform.claude.com/oauth/code/callback';
export const SCOPES = ['user:profile', 'user:inference'];

export interface OAuthTokens {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: number;
}

export interface Pkce {
  verifier: string;
  challenge: string;
  state: string;
}

export function createPkce(): Pkce {
  const verifier = crypto.randomBytes(32).toString('base64url');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  const state = crypto.randomBytes(32).toString('base64url');
  return { verifier, challenge, state };
}

export function authorizeUrl(pkce: Pkce, redirectUri: string): string {
  const url = new URL(AUTHORIZE_URL);
  url.searchParams.append('code', 'true');
  url.searchParams.append('client_id', CLIENT_ID);
  url.searchParams.append('response_type', 'code');
  url.searchParams.append('redirect_uri', redirectUri);
  url.searchParams.append('scope', SCOPES.join(' '));
  url.searchParams.append('code_challenge', pkce.challenge);
  url.searchParams.append('code_challenge_method', 'S256');
  url.searchParams.append('state', pkce.state);
  return url.toString();
}

export function splitManualCode(pasted: string): { code: string; state?: string } {
  const trimmed = pasted.trim();
  const hash = trimmed.indexOf('#');
  if (hash === -1) {
    return { code: trimmed };
  }
  return { code: trimmed.slice(0, hash), state: trimmed.slice(hash + 1) };
}

export function parseTokenResponse(raw: unknown, now: number): OAuthTokens | undefined {
  if (typeof raw !== 'object' || raw === null) {
    return undefined;
  }
  const body = raw as Record<string, unknown>;
  const accessToken = body['access_token'] ?? body['accessToken'];
  if (typeof accessToken !== 'string' || accessToken.length === 0) {
    return undefined;
  }
  const refreshToken = body['refresh_token'] ?? body['refreshToken'];
  const expiresIn = body['expires_in'] ?? body['expiresIn'];
  return {
    accessToken,
    refreshToken: typeof refreshToken === 'string' && refreshToken.length > 0 ? refreshToken : undefined,
    expiresAt: typeof expiresIn === 'number' && Number.isFinite(expiresIn) ? now + expiresIn * 1000 : undefined,
  };
}

async function postToken(payload: Record<string, unknown>): Promise<OAuthTokens> {
  const response = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Token endpoint returned HTTP ${response.status}: ${text.slice(0, 200)}`);
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('Token endpoint returned a non-JSON body');
  }
  const tokens = parseTokenResponse(parsed, Date.now());
  if (tokens === undefined) {
    throw new Error('Token endpoint returned no access token');
  }
  return tokens;
}

export function exchangeCode(options: {
  code: string;
  verifier: string;
  state: string;
  redirectUri: string;
}): Promise<OAuthTokens> {
  return postToken({
    grant_type: 'authorization_code',
    code: options.code,
    redirect_uri: options.redirectUri,
    client_id: CLIENT_ID,
    code_verifier: options.verifier,
    state: options.state,
  });
}

export function refreshTokens(refreshToken: string): Promise<OAuthTokens> {
  return postToken({
    grant_type: 'refresh_token',
    refresh_token: refreshToken,
    client_id: CLIENT_ID,
  });
}

const CLOSE_PAGE = `<!doctype html><meta charset="utf-8"><title>Claude Usage</title>
<style>body{font:15px -apple-system,Segoe UI,sans-serif;display:grid;place-items:center;height:100vh;margin:0;background:#1c1b19;color:#e8e5e0}
div{text-align:center}h1{font-size:17px;font-weight:600;margin:0 0 6px}p{margin:0;opacity:.65;font-size:13px}</style>
<div><h1>{{HEADING}}</h1><p>{{BODY}}</p></div>`;

function respond(response: http.ServerResponse, status: number, heading: string, body: string): void {
  response.writeHead(status, { 'Content-Type': 'text/html; charset=utf-8' });
  response.end(CLOSE_PAGE.replace('{{HEADING}}', heading).replace('{{BODY}}', body));
}

export interface LoopbackListener {
  redirectUri: string;
  waitForCode(): Promise<string>;
  dispose(): void;
}

export async function startLoopbackListener(pkce: Pkce): Promise<LoopbackListener> {
  let settle: ((code: string) => void) | undefined;
  let fail: ((error: Error) => void) | undefined;
  const received = new Promise<string>((resolve, reject) => {
    settle = resolve;
    fail = reject;
  });

  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? '/', 'http://localhost');
    if (url.pathname !== '/callback') {
      respond(response, 404, 'Not found', 'This page is not part of the sign-in flow.');
      return;
    }
    const error = url.searchParams.get('error');
    if (error) {
      respond(response, 400, 'Sign-in failed', url.searchParams.get('error_description') ?? error);
      fail?.(new Error(url.searchParams.get('error_description') ?? error));
      return;
    }
    const code = url.searchParams.get('code');
    const state = url.searchParams.get('state');
    if (!code) {
      respond(response, 400, 'Sign-in failed', 'The redirect carried no authorization code.');
      fail?.(new Error('No authorization code in the redirect'));
      return;
    }
    if (state !== pkce.state) {
      respond(response, 400, 'Sign-in failed', 'State mismatch. Start the sign-in again.');
      fail?.(new Error('OAuth state mismatch'));
      return;
    }
    respond(response, 200, 'Signed in to Claude Usage', 'You can close this tab and return to your editor.');
    settle?.(code);
  });

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      server.removeListener('error', reject);
      resolve();
    });
  });

  const address = server.address() as AddressInfo;
  return {
    redirectUri: `http://localhost:${address.port}/callback`,
    waitForCode: () => received,
    dispose: () => server.close(),
  };
}
