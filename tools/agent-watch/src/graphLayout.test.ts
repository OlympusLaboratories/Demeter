import { describe, expect, it } from 'vitest';
import { NODE_WIDTH, layoutForest, layoutTree } from './graphLayout';
import type { AgentNode } from './model';

function node(id: string, children: AgentNode[] = []): AgentNode {
  return { id, kind: 'agent', label: id, status: 'done', events: [], children };
}

describe('layoutTree', () => {
  it('places depth on the horizontal axis so wide fan-outs scroll vertically', () => {
    const wide = node('root', Array.from({ length: 27 }, (_unused, index) => node(`child-${index}`)));
    const layout = layoutTree(wide);

    expect(layout.nodes).toHaveLength(28);
    const root = layout.nodes.find((candidate) => candidate.id === 'root');
    const children = layout.nodes.filter((candidate) => candidate.id.startsWith('child-'));
    expect(root?.x).toBe(0);
    expect(new Set(children.map((child) => child.x)).size).toBe(1);
    expect(children[0]?.x).toBeGreaterThan(root?.x ?? 0);
    expect(new Set(children.map((child) => child.y)).size).toBe(27);
    expect(layout.height).toBeGreaterThan(layout.width);
  });

  it('emits one edge per parent-child pair, anchored to node borders', () => {
    const layout = layoutTree(node('root', [node('a'), node('b')]));
    expect(layout.edges).toHaveLength(2);
    const edge = layout.edges[0];
    expect(edge?.fromX).toBe(NODE_WIDTH);
    expect(edge?.toX).toBeGreaterThan(edge?.fromX ?? 0);
  });

  it('normalizes coordinates so nothing renders at a negative offset', () => {
    const layout = layoutTree(node('root', [node('a'), node('b'), node('c')]));
    for (const positioned of layout.nodes) {
      expect(positioned.x).toBeGreaterThanOrEqual(0);
      expect(positioned.y).toBeGreaterThanOrEqual(0);
    }
  });
});

describe('layoutForest', () => {
  it('renders sibling sessions as separate roots with no shared parent', () => {
    const layout = layoutForest([node('session-1', [node('a')]), node('session-2')]);

    expect(layout.nodes.map((positioned) => positioned.id).sort()).toEqual(['a', 'session-1', 'session-2']);
    expect(layout.edges).toHaveLength(1);
    expect(layout.edges[0]?.from).toBe('session-1');
    const roots = layout.nodes.filter((positioned) => positioned.id.startsWith('session-'));
    expect(new Set(roots.map((root) => root.x))).toEqual(new Set([0]));
  });

  it('returns an empty layout for no sessions', () => {
    expect(layoutForest([])).toEqual({ nodes: [], edges: [], width: 0, height: 0 });
  });
});
