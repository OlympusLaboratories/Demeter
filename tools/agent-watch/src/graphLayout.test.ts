import { describe, expect, it } from 'vitest';
import { NODE_WIDTH, layoutForest, layoutTree } from './graphLayout';
import { propagateActivity } from './model';
import { edgeClass } from './nodeChrome';
import type { AgentNode } from './model';

function node(id: string, children: AgentNode[] = []): AgentNode {
  return { id, kind: 'agent', label: id, status: 'done', events: [], children };
}

describe('layoutTree', () => {
  it('places depth on the horizontal axis so wide fan-outs scroll vertically', () => {
    const wide = node('root', Array.from({ length: 27 }, (_unused, index) => node(`child-${index}`)));
    const layout = layoutTree(wide, { autoCollapseThreshold: 1000, initialDepth: 99 });

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

describe('progressive expansion', () => {
  function wide(count: number): AgentNode {
    return node('phase', Array.from({ length: count }, (_u, index) => node(`agent-${index}`)));
  }

  it('hides the children of a layer wider than the threshold, and says how many', () => {
    const layout = layoutTree(wide(90), { autoCollapseThreshold: 12, initialDepth: 99 });

    expect(layout.nodes).toHaveLength(1);
    const phase = layout.nodes[0];
    expect(phase?.expanded).toBe(false);
    expect(phase?.hiddenChildren).toBe(90);
    expect(phase?.totalChildren).toBe(90);
  });

  it('expands that layer when explicitly overridden', () => {
    const layout = layoutTree(wide(90), {
      autoCollapseThreshold: 12,
      initialDepth: 99,
      overrides: new Map([['phase', true]]),
    });

    expect(layout.nodes).toHaveLength(91);
    expect(layout.nodes[0]?.expanded).toBe(true);
    expect(layout.nodes[0]?.hiddenChildren).toBe(0);
  });

  it('collapses a narrow layer when explicitly overridden shut', () => {
    const layout = layoutTree(wide(3), {
      autoCollapseThreshold: 12,
      initialDepth: 99,
      overrides: new Map([['phase', false]]),
    });

    expect(layout.nodes).toHaveLength(1);
    expect(layout.nodes[0]?.hiddenChildren).toBe(3);
  });

  it('leaves a narrow layer open by default', () => {
    const layout = layoutTree(wide(5), { autoCollapseThreshold: 12, initialDepth: 99 });
    expect(layout.nodes).toHaveLength(6);
    expect(layout.nodes[0]?.expanded).toBe(true);
  });

  it('reports zero children for a leaf and treats it as expanded', () => {
    const layout = layoutTree(node('leaf'));
    expect(layout.nodes[0]?.totalChildren).toBe(0);
    expect(layout.nodes[0]?.expanded).toBe(true);
    expect(layout.nodes[0]?.hiddenChildren).toBe(0);
  });

  it('lets a 96-agent run open one phase at a time', () => {
    const run = node('workflow', [
      node('Review', Array.from({ length: 6 }, (_u, i) => node(`r${i}`))),
      node('Verify', Array.from({ length: 90 }, (_u, i) => node(`v${i}`))),
    ]);

    const shut = layoutTree(run, { autoCollapseThreshold: 12, initialDepth: 99 });
    expect(shut.nodes.find((n) => n.id === 'Review')?.expanded).toBe(true);
    expect(shut.nodes.find((n) => n.id === 'Verify')?.expanded).toBe(false);
    expect(shut.nodes.find((n) => n.id === 'Verify')?.hiddenChildren).toBe(90);
    expect(shut.nodes).toHaveLength(9);

    const opened = layoutTree(run, {
      autoCollapseThreshold: 12,
      initialDepth: 99,
      overrides: new Map([['Verify', true]]),
    });
    expect(opened.nodes).toHaveLength(99);
    expect(opened.height).toBeGreaterThan(shut.height * 3);
  });
});

describe('initial depth', () => {
  function run(): AgentNode {
    return node('session', [
      node('workflow', [
        node('Review', [node('r0'), node('r1')]),
        node('Verify', [node('v0'), node('v1')]),
      ]),
    ]);
  }

  it('shows sessions and one level below them by default', () => {
    const layout = layoutForest([run()]);
    expect(layout.nodes.map((positioned) => positioned.id)).toEqual(['session', 'workflow']);
    expect(layout.nodes.find((positioned) => positioned.id === 'workflow')?.expanded).toBe(false);
    expect(layout.nodes.find((positioned) => positioned.id === 'workflow')?.hiddenChildren).toBe(2);
  });

  it('shows sessions alone at depth 0', () => {
    const layout = layoutForest([run()], { initialDepth: 0 });
    expect(layout.nodes.map((positioned) => positioned.id)).toEqual(['session']);
    expect(layout.nodes[0]?.hiddenChildren).toBe(1);
  });

  it('opens one branch at a time without disturbing its siblings', () => {
    const layout = layoutForest([run()], { overrides: new Map([['workflow', true]]) });
    expect(layout.nodes.map((positioned) => positioned.id)).toEqual([
      'session',
      'workflow',
      'Review',
      'Verify',
    ]);
    expect(layout.nodes.find((positioned) => positioned.id === 'Review')?.expanded).toBe(false);
  });

  it('keeps a deep layout small enough to read without zooming out', () => {
    const wide = node('session', [
      node('workflow', Array.from({ length: 8 }, (_u, index) =>
        node(`phase-${index}`, Array.from({ length: 40 }, (_v, inner) => node(`a-${index}-${inner}`))),
      )),
    ]);

    const initial = layoutForest([wide]);
    const everything = layoutForest([wide], { initialDepth: 99, autoCollapseThreshold: 1000 });

    expect(initial.nodes).toHaveLength(2);
    expect(everything.nodes.length).toBeGreaterThan(300);
    expect(initial.height).toBeLessThan(everything.height / 50);
  });

  it('still lets an explicit override win over the depth rule', () => {
    const layout = layoutForest([run()], {
      initialDepth: 0,
      overrides: new Map([['session', true]]),
    });
    expect(layout.nodes.map((positioned) => positioned.id)).toEqual(['session', 'workflow']);
  });
});

describe('edges carry the activity of what they point at', () => {
  function tree(): AgentNode {
    const leaf: AgentNode = { id: 'leaf', kind: 'agent', label: 'leaf', status: 'live', events: [], children: [] };
    const failed: AgentNode = { id: 'failed', kind: 'agent', label: 'failed', status: 'error', events: [], children: [leaf] };
    const quiet: AgentNode = { id: 'quiet', kind: 'agent', label: 'quiet', status: 'done', events: [], children: [] };
    return { id: 'root', kind: 'session', label: 'root', status: 'done', events: [], children: [failed, quiet] };
  }

  it('does not break the live path where it passes through a failure', () => {
    const root = tree();
    propagateActivity(root);
    const layout = layoutTree(root, { autoCollapseThreshold: 1000, initialDepth: 99 });
    const classes = Object.fromEntries(layout.edges.map((edge) => [edge.to, edgeClass(edge.toStatus)]));

    expect(classes['failed']).toBe('edge live');
    expect(classes['leaf']).toBe('edge live');
    expect(classes['quiet']).toBe('edge');
  });

  it('matches every edge to the activity of the node it reaches', () => {
    const root = tree();
    propagateActivity(root);
    const layout = layoutTree(root, { autoCollapseThreshold: 1000, initialDepth: 99 });
    const byId = new Map(layout.nodes.map((node) => [node.id, node]));

    for (const edge of layout.edges) {
      const target = byId.get(edge.to);
      expect(edge.toStatus).toBe(target?.activity ?? target?.status);
    }
  });

  it('gives a collapsed parent the green of the live descendant it is hiding', () => {
    const root = tree();
    propagateActivity(root);
    const layout = layoutTree(root, { overrides: new Map([['failed', false]]), initialDepth: 99 });

    expect(layout.nodes.some((node) => node.id === 'leaf')).toBe(false);
    const toFailed = layout.edges.find((edge) => edge.to === 'failed');
    expect(edgeClass(toFailed!.toStatus)).toBe('edge live');
  });
});

describe('edgeClass', () => {
  it('names only the two statuses that mean work is happening', () => {
    expect(edgeClass('live')).toBe('edge live');
    expect(edgeClass('running')).toBe('edge running');
    for (const quiet of ['done', 'error', 'idle'] as const) {
      expect(edgeClass(quiet)).toBe('edge');
    }
  });
});

describe('arriving at a tree with work in it', () => {
  function chain(statuses: ('done' | 'live')[]): AgentNode {
    let built: AgentNode | undefined;
    for (const status of [...statuses].reverse()) {
      built = {
        id: `n${statuses.indexOf(status)}-${status}-${Math.random()}`,
        kind: 'agent',
        label: status,
        status,
        events: [],
        children: built ? [built] : [],
      };
    }
    return built as AgentNode;
  }

  it('opens the path down to a working node that depth alone would have hidden', () => {
    const root = chain(['done', 'done', 'done', 'live']);
    propagateActivity(root);
    const layout = layoutTree(root, { initialDepth: 1 });

    expect(layout.nodes).toHaveLength(4);
    expect(layout.nodes.every((entry) => entry.status === 'live')).toBe(true);
  });

  it('leaves a quiet branch collapsed at the usual depth', () => {
    const root = chain(['done', 'done', 'done', 'done']);
    propagateActivity(root);

    expect(layoutTree(root, { initialDepth: 1 }).nodes).toHaveLength(2);
  });

  it('does not let an active fan-out flood the canvas', () => {
    const wide: AgentNode = {
      id: 'band',
      kind: 'phase',
      label: 'Verify',
      status: 'done',
      events: [],
      children: [...Array(90)].map((_, index) => ({
        id: `a${index}`,
        kind: 'agent' as const,
        label: `a${index}`,
        status: 'live' as const,
        events: [],
        children: [],
      })),
    };
    propagateActivity(wide);

    const layout = layoutTree(wide, { initialDepth: 1 });
    expect(layout.nodes).toHaveLength(1);
    expect(layout.nodes[0]?.status).toBe('live');
    expect(layout.nodes[0]?.hiddenChildren).toBe(90);
  });

  it('does not spring open a branch whose only claim to activity is a stale launch', () => {
    const stale: AgentNode = {
      id: 'stale-root',
      kind: 'session',
      label: 'month old',
      status: 'done',
      events: [],
      children: [
        {
          id: 'stuck',
          kind: 'agent',
          label: 'never returned',
          status: 'running',
          events: [],
          children: [
            { id: 'deep', kind: 'agent', label: 'deep', status: 'done', events: [], children: [] },
          ],
        },
      ],
    };
    propagateActivity(stale);

    expect(stale.status).toBe('running');
    expect(layoutTree(stale, { initialDepth: 1 }).nodes).toHaveLength(2);
  });

  it('still obeys a collapse you asked for by hand', () => {
    const root = chain(['done', 'live']);
    propagateActivity(root);
    const layout = layoutTree(root, { overrides: new Map([[root.id, false]]), initialDepth: 1 });

    expect(layout.nodes).toHaveLength(1);
  });
});
