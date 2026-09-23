import { describe, expect, it } from 'vitest';
import { isUsable, parseCredentials } from './claudeCodeCreds';

describe('parseCredentials', () => {
  it('reads the shape Claude Code stores', () => {
    const token = parseCredentials(
      JSON.stringify({
        claudeAiOauth: { accessToken: 'sk-ant-oat01-x', refreshToken: 'sk-ant-ort01-y', expiresAt: 1_790_162_410_863 },
        organizationUuid: 'abc',
      }),
    );
    expect(token).toEqual({ accessToken: 'sk-ant-oat01-x', expiresAt: 1_790_162_410_863 });
  });

  it('accepts a credential with no expiry', () => {
    expect(parseCredentials(JSON.stringify({ claudeAiOauth: { accessToken: 'x' } }))).toEqual({
      accessToken: 'x',
      expiresAt: undefined,
    });
  });

  it('rejects anything it cannot use', () => {
    expect(parseCredentials('not json')).toBeUndefined();
    expect(parseCredentials('null')).toBeUndefined();
    expect(parseCredentials('{}')).toBeUndefined();
    expect(parseCredentials(JSON.stringify({ claudeAiOauth: {} }))).toBeUndefined();
    expect(parseCredentials(JSON.stringify({ claudeAiOauth: { accessToken: '' } }))).toBeUndefined();
  });
});

describe('isUsable', () => {
  const now = 1_000_000;

  it('accepts a token with room left before it expires', () => {
    expect(isUsable({ accessToken: 'x', expiresAt: now + 600_000 }, now)).toBe(true);
  });

  it('accepts a token with no stated expiry', () => {
    expect(isUsable({ accessToken: 'x' }, now)).toBe(true);
  });

  it('rejects an expired token and one inside the skew window', () => {
    expect(isUsable({ accessToken: 'x', expiresAt: now - 1 }, now)).toBe(false);
    expect(isUsable({ accessToken: 'x', expiresAt: now + 30_000 }, now)).toBe(false);
  });

  it('rejects a missing token', () => {
    expect(isUsable(undefined, now)).toBe(false);
  });
});
