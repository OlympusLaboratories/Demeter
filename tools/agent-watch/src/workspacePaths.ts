export function isWithin(parent: string, child: string): boolean {
  const normalise = (value: string): string => value.replace(/\/+$/, '');
  const base = normalise(parent);
  const target = normalise(child);
  return target === base || target.startsWith(`${base}/`);
}

export function isInAnyFolder(folders: string[], dir: string | undefined): boolean {
  if (!dir) return false;
  return folders.some((folder) => isWithin(folder, dir));
}
