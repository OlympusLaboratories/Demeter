export interface ChildArrival {
  id: string;
  childCount: number;
}

export class FirstChildrenWatch {
  private seen = new Set<string>();
  private hadChildren = new Set<string>();

  clear(): void {
    this.seen = new Set();
    this.hadChildren = new Set();
  }

  claim(nodes: ChildArrival[]): string[] {
    const seen = new Set<string>();
    const hadChildren = new Set<string>();
    const arrivals: string[] = [];

    for (const node of nodes) {
      seen.add(node.id);
      const knew = this.hadChildren.has(node.id);
      if (knew) hadChildren.add(node.id);
      if (node.childCount === 0) continue;
      hadChildren.add(node.id);
      if (!knew && this.seen.has(node.id)) arrivals.push(node.id);
    }

    this.seen = seen;
    this.hadChildren = hadChildren;
    return arrivals;
  }
}
