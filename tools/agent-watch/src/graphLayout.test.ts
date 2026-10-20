import { describe, expect, it } from 'vitest';
import { NODE_WIDTH, layoutForest, layoutTree } from './graphLayout';
import type { AgentNode } from './model';

function node(id: string, children: AgentNode[] = []): AgentNode {
  return { id, kind: 'agent', label: id, status: 'done', events: [], children };
}

describe('layoutTree', () => {
  it('places depth on the horizontal axis so wide fan-outs scroll vertically', () => {
    const wide = node('root', Array.from({ length: 27 }, (_unused, index) => node(`child-${index}`)));
    const layout = layoutTree(wide, { groupThreshold: 1000 });

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

describe('wide fan-out collapsing', () => {
  function wide(count: number): AgentNode {
    return node('phase', Array.from({ length: count }, (_u, index) => node(`agent-${index}`)));
  }

  it('replaces the tail of a wide layer with one counted group node', () => {
    const layout = layoutTree(wide(90), { groupThreshold: 12 });
    const children = layout.nodes.filter((positioned) => positioned.id !== 'phase');

    expect(children).toHaveLength(13);
    const group = children.find((child) => child.id.startsWith('group:'));
    expect(group?.label).toBe('+78 more');
    expect(group?.group?.parentId).toBe('phase');
  });

  it('shows every child once its parent is expanded', () => {
    const layout = layoutTree(wide(90), { groupThreshold: 12, expanded: new Set(['phase']) });
    expect(layout.nodes).toHaveLength(91);
    expect(layout.nodes.some((positioned) => positioned.id.startsWith('group:'))).toBe(false);
  });

  it('leaves a layer at or under the threshold untouched', () => {
    const layout = layoutTree(wide(12), { groupThreshold: 12 });
    expect(layout.nodes).toHaveLength(13);
    expect(layout.nodes.some((positioned) => positioned.id.startsWith('group:'))).toBe(false);
  });

  it('surfaces running work in the collapsed group so it is never hidden silently', () => {
    const children = Array.from({ length: 30 }, (_u, index) => node(`agent-${index}`));
    children[20] = { ...children[20]!, status: 'running' };
    const layout = layoutTree(node('phase', children), { groupThreshold: 5 });
    const group = layout.nodes.find((positioned) => positioned.id.startsWith('group:'));

    expect(group?.sublabel).toBe('1 running');
    expect(group?.status).toBe('running');
  });

  it('cuts a 96-agent run down to a scrollable height', () => {
    const run = node('workflow', [node('Review', Array.from({ length: 6 }, (_u, i) => node(`r${i}`))), node('Verify', Array.from({ length: 90 }, (_u, i) => node(`v${i}`)))]);
    const collapsed = layoutTree(run, { groupThreshold: 12 });
    const full = layoutTree(run, { groupThreshold: 1000 });

    expect(collapsed.height).toBeLessThan(full.height / 3);
  });
});
