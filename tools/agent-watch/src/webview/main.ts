import { NODE_HEIGHT, NODE_WIDTH } from '../graphLayout';
import type { AgentEvent, NodeStatus } from '../model';
import type { HostMessage, NodeDetail, ViewMessage, ViewState } from '../protocol';

declare function acquireVsCodeApi(): { postMessage(message: ViewMessage): void };

const vscode = acquireVsCodeApi();
const SVG_NS = 'http://www.w3.org/2000/svg';

const GLYPHS: Record<NodeStatus, string> = {
  live: '●',
  running: '◐',
  done: '✓',
  error: '✗',
  idle: '○',
};

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function svgEl<K extends keyof SVGElementTagNameMap>(tag: K): SVGElementTagNameMap[K] {
  return document.createElementNS(SVG_NS, tag);
}

function byId<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`missing element: ${id}`);
  return found as T;
}

function renderScope(state: ViewState): void {
  const repos = byId('repos');
  repos.replaceChildren();
  for (const repo of state.repos) {
    const chip = el('button', repo.slug === state.selectedRepo ? 'chip selected' : 'chip');
    chip.type = 'button';
    chip.append(document.createTextNode(repo.label));
    if (repo.liveCount > 0) chip.append(el('span', 'live', `●${repo.liveCount}`));
    chip.addEventListener('click', () => vscode.postMessage({ type: 'selectRepo', slug: repo.slug }));
    repos.append(chip);
  }

  const worktrees = byId('worktrees');
  worktrees.replaceChildren();
  for (const tree of state.worktrees) {
    const chip = el('button', tree.key === state.selectedWorktree ? 'chip selected' : 'chip');
    chip.type = 'button';
    chip.append(document.createTextNode(tree.label));
    if (tree.liveCount > 0) chip.append(el('span', 'live', `●${tree.liveCount}`));
    chip.addEventListener('click', () => vscode.postMessage({ type: 'selectWorktree', key: tree.key }));
    worktrees.append(chip);
  }
}

function renderStatus(state: ViewState): void {
  const status = byId('status');
  status.replaceChildren();

  const liveTotal = state.worktrees.reduce((total, tree) => total + tree.liveCount, 0);
  if (liveTotal > 0) {
    const dot = el('span', 'dot', `● ${liveTotal} live`);
    status.append(dot);
  }

  const stamp = new Date(state.updatedAtMs).toLocaleTimeString();
  status.append(
    el(
      'span',
      undefined,
      state.loading ? 'refreshing…' : `updated ${stamp} · watching ${state.watchedCount} paths`,
    ),
  );
}

function renderGraph(state: ViewState): void {
  const svg = document.getElementById('graph') as SVGSVGElement | null;
  const empty = byId('empty');
  if (!svg) return;
  svg.replaceChildren();

  if (state.graph.nodes.length === 0) {
    empty.classList.remove('hidden');
    empty.textContent = state.message
      ? state.message
      : state.loading
        ? 'Scanning…'
        : 'No sessions in the selected scope.';
    svg.setAttribute('width', '0');
    svg.setAttribute('height', '0');
    return;
  }

  empty.classList.add('hidden');
  const pad = 20;
  svg.setAttribute('width', String(state.graph.width + pad * 2));
  svg.setAttribute('height', String(state.graph.height + pad * 2));

  for (const edge of state.graph.edges) {
    const path = svgEl('path');
    const midX = (edge.fromX + edge.toX) / 2;
    path.setAttribute(
      'd',
      `M${edge.fromX + pad},${edge.fromY + pad} C${midX + pad},${edge.fromY + pad} ${midX + pad},${edge.toY + pad} ${edge.toX + pad},${edge.toY + pad}`,
    );
    path.setAttribute('class', 'edge');
    svg.append(path);
  }

  for (const node of state.graph.nodes) {
    const group = svgEl('g');
    group.setAttribute('class', `node ${node.status}`);
    group.setAttribute('transform', `translate(${node.x + pad},${node.y + pad})`);

    const rect = svgEl('rect');
    rect.setAttribute('width', String(NODE_WIDTH));
    rect.setAttribute('height', String(NODE_HEIGHT));
    group.append(rect);

    const glyph = svgEl('text');
    glyph.setAttribute('class', 'glyph');
    glyph.setAttribute('x', '10');
    glyph.setAttribute('y', '19');
    glyph.textContent = GLYPHS[node.status];
    group.append(glyph);

    const label = svgEl('text');
    label.setAttribute('class', 'label');
    label.setAttribute('x', '26');
    label.setAttribute('y', '19');
    label.textContent = truncate(node.label, 22);
    group.append(label);

    const sub = svgEl('text');
    sub.setAttribute('class', 'sublabel');
    sub.setAttribute('x', '26');
    sub.setAttribute('y', '34');
    const counts = node.childCount > 0 ? `${node.childCount} agents` : `${node.eventCount} events`;
    sub.textContent = truncate(node.sublabel ? `${node.sublabel} · ${counts}` : counts, 26);
    group.append(sub);

    const title = svgEl('title');
    title.textContent = node.sublabel ? `${node.label}\n${node.sublabel}` : node.label;
    group.append(title);

    group.addEventListener('click', () => vscode.postMessage({ type: 'selectNode', id: node.id }));
    svg.append(group);
  }
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function renderDetail(detail: NodeDetail): void {
  byId('modal-title').textContent = detail.sublabel ? `${detail.label} — ${detail.sublabel}` : detail.label;
  const body = byId('modal-body');
  body.replaceChildren();

  if (detail.events.length === 0) {
    body.append(el('p', undefined, 'No recorded activity for this node.'));
  }

  for (const event of detail.events) {
    body.append(renderEvent(event));
  }
  byId('overlay').classList.remove('hidden');
}

function renderEvent(event: AgentEvent): HTMLElement {
  const wrapper = el('div', `event ${event.kind}${event.isError ? ' err' : ''}`);
  const head = el('div', 'head');

  if (event.kind === 'tool') {
    head.append(el('span', 'tool', event.name ?? 'tool'));
    if (event.summary) head.append(el('span', 'summary', event.summary));
  } else if (event.kind === 'thinking') {
    head.append(el('span', 'tool', 'thinking'));
    head.append(
      el('span', 'summary', event.text ? '' : `${event.thinkingChars ?? 0} chars withheld by the API`),
    );
  } else {
    head.append(el('span', 'tool', 'said'));
  }
  wrapper.append(head);

  const text = event.kind === 'tool' ? event.result : event.text;
  if (text) {
    const pre = el('pre');
    pre.textContent = event.resultTruncated ? `${text}\n…truncated` : text;
    wrapper.append(pre);
  }
  return wrapper;
}

function wire(): void {
  byId('modal-close').addEventListener('click', () => byId('overlay').classList.add('hidden'));
  byId('overlay').addEventListener('click', (event) => {
    if (event.target === byId('overlay')) byId('overlay').classList.add('hidden');
  });
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') byId('overlay').classList.add('hidden');
  });

  window.addEventListener('message', (event: MessageEvent<HostMessage>) => {
    const message = event.data;
    if (message.type === 'state') {
      renderScope(message.state);
      renderStatus(message.state);
      renderGraph(message.state);
    } else if (message.type === 'detail') {
      renderDetail(message.detail);
    }
  });

  vscode.postMessage({ type: 'ready' });
}

wire();
