const SEMVER = /^(\d+)\.(\d+)\.(\d+)/;

export function parseVersion(value: string): [number, number, number] | undefined {
  const match = SEMVER.exec(value);
  if (!match) {
    return undefined;
  }
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

export function compareVersions(a: string, b: string): number {
  const left = parseVersion(a);
  const right = parseVersion(b);
  if (!left || !right) {
    return 0;
  }
  for (let i = 0; i < 3; i++) {
    const diff = (left[i] ?? 0) - (right[i] ?? 0);
    if (diff !== 0) {
      return diff > 0 ? 1 : -1;
    }
  }
  return 0;
}

export function newerInstalledVersion(
  entries: string[],
  extensionId: string,
  running: string,
): string | undefined {
  const prefix = `${extensionId}-`;
  let newest = running;
  for (const entry of entries) {
    if (!entry.startsWith(prefix)) {
      continue;
    }
    const candidate = entry.slice(prefix.length);
    if (parseVersion(candidate) && compareVersions(candidate, newest) > 0) {
      newest = candidate;
    }
  }
  return compareVersions(newest, running) > 0 ? newest : undefined;
}
