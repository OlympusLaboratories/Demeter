import type { Dirent } from 'node:fs';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';

export interface SessionFile {
  sessionId: string;
  transcriptPath: string;
  mtimeMs: number;
  size: number;
}

export interface ProjectDir {
  slug: string;
  dir: string;
  newestMtimeMs: number;
  sessions: SessionFile[];
}

export async function scanProjects(projectsDir: string): Promise<ProjectDir[]> {
  let entries: Dirent[];
  try {
    entries = await fs.readdir(projectsDir, { withFileTypes: true });
  } catch {
    return [];
  }

  const projects: ProjectDir[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.isSymbolicLink()) continue;
    const dir = path.join(projectsDir, entry.name);
    const sessions = await scanSessions(dir);
    if (sessions.length === 0) continue;
    const newestMtimeMs = sessions.reduce((newest, session) => Math.max(newest, session.mtimeMs), 0);
    projects.push({ slug: entry.name, dir, newestMtimeMs, sessions });
  }

  projects.sort((left, right) => right.newestMtimeMs - left.newestMtimeMs);
  return projects;
}

async function scanSessions(dir: string): Promise<SessionFile[]> {
  let entries: Dirent[];
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }

  const sessions: SessionFile[] = [];
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.jsonl')) continue;
    const transcriptPath = path.join(dir, entry.name);
    try {
      const stats = await fs.stat(transcriptPath);
      sessions.push({
        sessionId: entry.name.replace(/\.jsonl$/, ''),
        transcriptPath,
        mtimeMs: stats.mtimeMs,
        size: stats.size,
      });
    } catch {
      continue;
    }
  }

  sessions.sort((left, right) => right.mtimeMs - left.mtimeMs);
  return sessions;
}

export function withinDays(mtimeMs: number, days: number, nowMs: number): boolean {
  return nowMs - mtimeMs <= days * 86_400_000;
}
