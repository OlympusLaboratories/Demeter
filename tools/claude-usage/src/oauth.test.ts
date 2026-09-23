import { describe, expect, it } from 'vitest';
import { CLIENT_ID, authorizeUrl, createPkce, parseTokenResponse, splitManualCode } from './oauth';

describe('createPkce', () => {
  it('derives an S256 challenge from a fresh verifier', () => {
    const first = createPkce();
    const second = createPkce();
    expect(first.verifier).not.toBe(second.verifier);
    expect(first.state).not.toBe(second.state);
    expect(first.challenge).not.toContain('=');
    expect(first.challenge).not.toContain('+');
    expect(first.challenge).not.toContain('/');
  });
});

describe('authorizeUrl', () => {
  it('carries every parameter the authorize endpoint expects', () => {
    const pkce = createPkce();
    const url = new URL(authorizeUrl(pkce, 'http://localhost:51234/callback'));
    expect(url.origin + url.pathname).toBe('https://claude.com/cai/oauth/authorize');
    expect(url.searchParams.get('code')).toBe('true');
    expect(url.searchParams.get('client_id')).toBe(CLIENT_ID);
    expect(url.searchParams.get('response_type')).toBe('code');
    expect(url.searchParams.get('redirect_uri')).toBe('http://localhost:51234/callback');
    expect(url.searchParams.get('code_challenge')).toBe(pkce.challenge);
    expect(url.searchParams.get('code_challenge_method')).toBe('S256');
    expect(url.searchParams.get('state')).toBe(pkce.state);
    expect(url.searchParams.get('scope')).toContain('user:profile');
  });
});

describe('splitManualCode', () => {
  it('splits the code#state form the manual page shows', () => {
    expect(splitManualCode('  abc#xyz  ')).toEqual({ code: 'abc', state: 'xyz' });
  });

  it('accepts a bare code', () => {
    expect(splitManualCode('abc')).toEqual({ code: 'abc' });
  });
});

describe('parseTokenResponse', () => {
  it('reads snake_case fields and turns expires_in into an absolute stamp', () => {
    const tokens = parseTokenResponse({ access_token: 'a', refresh_token: 'r', expires_in: 60 }, 1_000)!;
    expect(tokens).toEqual({ accessToken: 'a', refreshToken: 'r', expiresAt: 61_000 });
  });

  it('tolerates a response with no refresh token or expiry', () => {
    expect(parseTokenResponse({ access_token: 'a' }, 0)).toEqual({
      accessToken: 'a',
      refreshToken: undefined,
      expiresAt: undefined,
    });
  });

  it('rejects a response with no access token', () => {
    expect(parseTokenResponse({ refresh_token: 'r' }, 0)).toBeUndefined();
    expect(parseTokenResponse({ access_token: '' }, 0)).toBeUndefined();
    expect(parseTokenResponse(null, 0)).toBeUndefined();
  });
});
