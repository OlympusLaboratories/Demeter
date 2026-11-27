import { type AgentNode, countNodes } from './model';

export interface Pruned {
  roots: AgentNode[];
  hidden: number;
}

export function newestActivityMs(node: AgentNode): number {
  let newest = node.activityMs ?? 0;
  for (const child of node.children) newest = Math.max(newest, newestActivityMs(child));
  return newest;
}

export function pruneStale(roots: AgentNode[], cutoffMs: number): Pruned {
  const survivors: AgentNode[] = [];
  let hidden = 0;

  for (const root of roots) {
    if (newestActivityMs(root) >= cutoffMs) survivors.push(root);
    else hidden += countNodes(root);
  }

  return { roots: survivors, hidden };
}
