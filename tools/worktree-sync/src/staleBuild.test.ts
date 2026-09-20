import { describe, expect, it } from 'vitest';
import { compareVersions, newerInstalledVersion, parseVersion } from './staleBuild';

const ID = 'dylanlarrabee.worktree-sync';

describe('compareVersions', () => {
  it('orders by patch, minor and major', () => {
    expect(compareVersions('0.1.5', '0.1.4')).toBe(1);
    expect(compareVersions('0.2.0', '0.1.9')).toBe(1);
    expect(compareVersions('1.0.0', '0.9.9')).toBe(1);
    expect(compareVersions('0.1.4', '0.1.5')).toBe(-1);
    expect(compareVersions('0.1.5', '0.1.5')).toBe(0);
  });

  it('does not compare 0.1.10 as older than 0.1.9', () => {
    expect(compareVersions('0.1.10', '0.1.9')).toBe(1);
  });
});

describe('parseVersion', () => {
  it('tolerates a platform suffix', () => {
    expect(parseVersion('0.1.5-darwin-arm64')).toEqual([0, 1, 5]);
  });

  it('rejects a non-version directory name', () => {
    expect(parseVersion('extensions.json')).toBeUndefined();
  });
});

describe('newerInstalledVersion', () => {
  const entries = [
    'extensions.json',
    'other.extension-9.9.9',
    `${ID}-0.1.1`,
    `${ID}-0.1.2`,
    `${ID}-0.1.10`,
    `${ID}-0.1.4`,
  ];

  it('reports the newest build when an older one is running', () => {
    expect(newerInstalledVersion(entries, ID, '0.1.1')).toBe('0.1.10');
  });

  it('reports nothing when the newest build is running', () => {
    expect(newerInstalledVersion(entries, ID, '0.1.10')).toBeUndefined();
  });

  it('reports nothing when the running build is newer than anything on disk', () => {
    expect(newerInstalledVersion(entries, ID, '0.2.0')).toBeUndefined();
  });

  it('ignores other extensions with higher versions', () => {
    expect(newerInstalledVersion([`other.extension-9.9.9`], ID, '0.1.1')).toBeUndefined();
  });

  it('copes with an empty extensions directory', () => {
    expect(newerInstalledVersion([], ID, '0.1.1')).toBeUndefined();
  });
});
