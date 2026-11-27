import { type AgentNode, type NodeStatus, countNodes } from './model';

export interface Pruned {
  roots: AgentNode[];
  hidden: number;
}

export function isActiveStatus(status: NodeStatus | undefined): boolean {
  return status === 'live' || status === 'running';
}

function worthKeeping(node: AgentNode): boolean {
  return isActiveStatus(node.activity ?? node.status);
}

export function pruneInactive(roots: AgentNode[]): Pruned {
  let kept = 0;
  let total = 0;

  const visit = (node: AgentNode): AgentNode | undefined => {
    const children: AgentNode[] = [];
    for (const child of node.children) {
      const survivor = visit(child);
      if (survivor) children.push(survivor);
    }
    if (children.length === 0 && !worthKeeping(node)) return undefined;
    kept += 1;
    return { ...node, children };
  };

  const survivors: AgentNode[] = [];
  for (const root of roots) {
    total += countNodes(root);
    const survivor = visit(root);
    if (survivor) survivors.push(survivor);
  }

  return { roots: survivors, hidden: total - kept };
}
