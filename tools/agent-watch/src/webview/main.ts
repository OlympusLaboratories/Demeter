import { NODE_HEIGHT, NODE_WIDTH } from '../graphLayout';
import {
  GLYPH_X,
  LABEL_BASELINE,
  SUBLABEL_BASELINE,
  TEXT_X,
  badgeBox,
  countsLabel,
  edgeClass,
  labelCapacity,
  openBox,
  sublabelCapacity,
} from '../nodeChrome';
import type { GraphLayout } from '../graphLayout';
import type { AgentEvent, NodeStatus } from '../model';
import type { SpeakerRole } from '../transcript';
import { moreLabel, previewOf } from '../preview';
import type { HostMessage, NodeDetail, ViewMessage, ViewState } from '../protocol';
import { clampZoom, zoomFactorFor } from '../zoom';
import { MIN_FIT_SCALE, expansionBoxes, frameBox, siblingBoxes } from '../focus';

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

function chipFor(
  kind: 'repo' | 'worktree',
  label: string,
  liveCount: number,
  selected: boolean,
  onPick: () => void,
  home = false,
): HTMLButtonElement {
  const classes = ['chip', kind];
  if (selected) classes.push('selected');
  if (home) classes.push('home');
  const chip = el('button', classes.join(' '));
  if (home) chip.title = 'The repo this window has open';
  chip.type = 'button';
  chip.append(document.createTextNode(label));
  if (liveCount > 0) chip.append(el('span', 'live', `●${liveCount}`));
  chip.addEventListener('click', () => {
    pendingFocus = undefined;
    onPick();
  });
  return chip;
}

function fillRow(rowId: string, chipsId: string, chips: HTMLButtonElement[]): void {
  const host = byId(chipsId);
  host.replaceChildren(...chips);
  byId(rowId).classList.toggle('hidden', chips.length === 0);
}

function renderScope(state: ViewState): void {
  fillRow(
    'repo-row',
    'repos',
    state.repos.map((repo) =>
      chipFor(
        'repo',
        repo.label,
        repo.liveCount,
        repo.slug === state.selectedRepo,
        () => vscode.postMessage({ type: 'selectRepo', slug: repo.slug }),
        repo.isWorkspace,
      ),
    ),
  );

  fillRow(
    'branch-row',
    'worktrees',
    state.worktrees.map((tree) =>
      chipFor('worktree', tree.label, tree.liveCount, tree.key === state.selectedWorktree, () =>
        vscode.postMessage({ type: 'selectWorktree', key: tree.key }),
      ),
    ),
  );
}

interface Viewport {
  k: number;
  tx: number;
  ty: number;
}

const view: Viewport = { k: 1, tx: 0, ty: 0 };
let lastLayout: GraphLayout = { nodes: [], edges: [], width: 0, height: 0 };
let userAdjusted = false;
let lastShape = '';
let zoomSensitivity = 1;
let onlyThisWindow = false;
let pendingFocus: { id: string; expanding: boolean } | undefined;

function applyTransform(): void {
  const root = document.getElementById('viewport');
  if (root) root.setAttribute('transform', `translate(${view.tx},${view.ty}) scale(${view.k})`);
  const level = document.getElementById('zoom-level');
  if (level) level.textContent = `${Math.round(view.k * 100)}%`;
}

function fitToView(): void {
  if (lastLayout.width <= 0 || lastLayout.height <= 0) return;
  const frame = frameBox(
    { x: 0, y: 0, width: lastLayout.width, height: lastLayout.height },
    canvasSize(),
    { minScale: MIN_FIT_SCALE },
  );
  view.k = frame.k;
  view.tx = frame.tx;
  view.ty = frame.ty;
  userAdjusted = false;
  applyTransform();
}

function canvasSize(): { width: number; height: number } {
  const canvas = byId('canvas');
  return { width: canvas.clientWidth, height: canvas.clientHeight };
}

function applyFocus(layout: GraphLayout): boolean {
  const request = pendingFocus;
  if (!request) return false;

  const node = layout.nodes.find((entry) => entry.id === request.id);
  if (!node || node.expanded !== request.expanding) return false;

  const boxes = request.expanding
    ? expansionBoxes(layout, request.id)
    : siblingBoxes(layout, request.id);
  if (!boxes) return false;

  const frame = frameBox(boxes.row, canvasSize(), {
    context: boxes.withParent,
    anchor: boxes.anchor,
  });
  pendingFocus = undefined;
  view.k = frame.k;
  view.tx = frame.tx;
  view.ty = frame.ty;
  userAdjusted = true;
  applyTransform();
  return true;
}

function zoomAt(factor: number, clientX: number, clientY: number): void {
  const canvas = byId('canvas');
  const rect = canvas.getBoundingClientRect();
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  const next = clampZoom(view.k * factor);
  if (next === view.k) return;
  view.tx = x - ((x - view.tx) / view.k) * next;
  view.ty = y - ((y - view.ty) / view.k) * next;
  view.k = next;
  userAdjusted = true;
  applyTransform();
}

function wireViewport(): void {
  const canvas = byId('canvas');
  let dragging = false;
  let originX = 0;
  let originY = 0;

  canvas.addEventListener('mousedown', (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    dragging = true;
    originX = event.clientX - view.tx;
    originY = event.clientY - view.ty;
    canvas.classList.add('grabbing');
  });
  window.addEventListener('mousemove', (event) => {
    if (!dragging) return;
    view.tx = event.clientX - originX;
    view.ty = event.clientY - originY;
    userAdjusted = true;
    applyTransform();
  });
  window.addEventListener('mouseup', () => {
    dragging = false;
    canvas.classList.remove('grabbing');
  });
  canvas.addEventListener(
    'wheel',
    (event) => {
      event.preventDefault();
      const factor = zoomFactorFor(
        {
          deltaY: event.deltaY,
          deltaMode: event.deltaMode,
          ctrlKey: event.ctrlKey,
          pageHeight: canvas.clientHeight,
        },
        zoomSensitivity,
      );
      if (factor !== 1) zoomAt(factor, event.clientX, event.clientY);
    },
    { passive: false },
  );

  byId('expand-all').addEventListener('click', () => {
    pendingFocus = undefined;
    vscode.postMessage({ type: 'toggleAll' });
  });
  byId('only-window').addEventListener('click', () => {
    pendingFocus = undefined;
    vscode.postMessage({ type: 'setOnlyThisWindow', value: !onlyThisWindow });
  });
  byId('fit').addEventListener('click', () => {
    pendingFocus = undefined;
    fitToView();
  });
  byId('zoom-in').addEventListener('click', () => {
    const rect = byId('canvas').getBoundingClientRect();
    zoomAt(1.2, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
  byId('zoom-out').addEventListener('click', () => {
    const rect = byId('canvas').getBoundingClientRect();
    zoomAt(1 / 1.2, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
}

function renderStatus(state: ViewState): void {
  onlyThisWindow = state.onlyThisWindow;
  byId('only-window').classList.toggle('on', state.onlyThisWindow);
  const status = byId('status-text');
  status.replaceChildren();

  const liveTotal = state.worktrees.reduce((total, tree) => total + tree.liveCount, 0);
  if (liveTotal > 0) {
    const dot = el('span', 'dot', `● ${liveTotal} live`);
    status.append(dot);
  }

  if (state.removedCount > 0) {
    const hidden = el('span', 'hidden-count', `${state.removedCount} deleted`);
    hidden.title = `${state.removedCount} session${state.removedCount === 1 ? '' : 's'} hidden: the git worktree or branch it ran on no longer exists. Turn off agentWatch.hideDeletedWork to show them.`;
    status.append(hidden);
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
        : state.repos.length === 0
          ? 'No Claude Code sessions found. Check agentWatch.projectsDir if your transcripts live elsewhere.'
          : state.worktrees.length === 0
            ? `No sessions in the last ${state.recentDays} days for this repo.`
            : 'No sessions in this worktree.';
    lastLayout = state.graph;
    lastShape = '';
    return;
  }

  empty.classList.add('hidden');
  const pad = 0;
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  const viewport = svgEl('g');
  viewport.setAttribute('id', 'viewport');
  svg.append(viewport);

  for (const edge of state.graph.edges) {
    const path = svgEl('path');
    const midX = (edge.fromX + edge.toX) / 2;
    path.setAttribute(
      'd',
      `M${edge.fromX + pad},${edge.fromY + pad} C${midX + pad},${edge.fromY + pad} ${midX + pad},${edge.toY + pad} ${edge.toX + pad},${edge.toY + pad}`,
    );
    path.setAttribute('class', edgeClass(edge.toStatus));
    viewport.append(path);
  }

  for (const node of state.graph.nodes) {
    const group = svgEl('g');
    group.setAttribute('class', `node ${node.status}${node.expanded ? '' : ' collapsed'}`);
    group.setAttribute('transform', `translate(${node.x + pad},${node.y + pad})`);

    const rect = svgEl('rect');
    rect.setAttribute('width', String(NODE_WIDTH));
    rect.setAttribute('height', String(NODE_HEIGHT));
    group.append(rect);

    const glyph = svgEl('text');
    glyph.setAttribute('class', 'glyph');
    glyph.setAttribute('x', String(GLYPH_X));
    glyph.setAttribute('y', String(LABEL_BASELINE));
    glyph.textContent = GLYPHS[node.status];
    group.append(glyph);

    const label = svgEl('text');
    label.setAttribute('class', 'label');
    label.setAttribute('x', String(TEXT_X));
    label.setAttribute('y', String(LABEL_BASELINE));
    const chrome = { badge: node.totalChildren > 0, open: node.kind === 'session' };
    label.textContent = truncate(node.label, labelCapacity(chrome));
    group.append(label);

    const sub = svgEl('text');
    sub.setAttribute('class', 'sublabel');
    sub.setAttribute('x', String(TEXT_X));
    sub.setAttribute('y', String(SUBLABEL_BASELINE));
    const counts = countsLabel(node.eventCount, node.childCount);
    sub.textContent = truncate(
      node.sublabel ? `${node.sublabel} · ${counts}` : counts,
      sublabelCapacity(chrome),
    );
    group.append(sub);

    const title = svgEl('title');
    title.textContent = node.sublabel ? `${node.label}\n${node.sublabel}` : node.label;
    group.append(title);

    if (chrome.open) {
      const box = openBox();
      const open = svgEl('g');
      open.setAttribute('class', 'open-chat');
      open.setAttribute('transform', `translate(${box.x},${box.y})`);

      const plate = svgEl('rect');
      plate.setAttribute('width', String(box.width));
      plate.setAttribute('height', String(box.height));
      plate.setAttribute('rx', '4');
      open.append(plate);

      const mark = svgEl('text');
      mark.setAttribute('x', String(box.width / 2));
      mark.setAttribute('y', String(box.height - 4));
      mark.setAttribute('text-anchor', 'middle');
      mark.textContent = '↗';
      open.append(mark);

      const hint = svgEl('title');
      hint.textContent = 'Open this chat session';
      open.append(hint);

      open.addEventListener('click', (event) => {
        event.stopPropagation();
        vscode.postMessage({ type: 'openSession', id: node.id });
      });
      group.append(open);
    }

    if (node.totalChildren > 0) {
      const box = badgeBox();
      const badge = svgEl('g');
      badge.setAttribute('class', 'badge');
      badge.setAttribute('transform', `translate(${box.x},${box.y})`);

      const pill = svgEl('rect');
      pill.setAttribute('width', String(box.width));
      pill.setAttribute('height', String(box.height));
      pill.setAttribute('rx', String(box.height / 2));
      badge.append(pill);

      const count = svgEl('text');
      count.setAttribute('x', String(box.width / 2));
      count.setAttribute('y', String(box.height - 4));
      count.setAttribute('text-anchor', 'middle');
      count.textContent = `${node.expanded ? '▾' : '▸'}${node.totalChildren}`;
      badge.append(count);

      const hint = svgEl('title');
      hint.textContent = node.expanded
        ? `Collapse ${node.totalChildren} children`
        : `Expand ${node.totalChildren} children`;
      badge.append(hint);

      badge.addEventListener('click', (event) => {
        event.stopPropagation();
        pendingFocus = { id: node.id, expanding: !node.expanded };
        vscode.postMessage({ type: 'toggleNode', id: node.id });
      });
      group.append(badge);
    }

    group.addEventListener('click', () => vscode.postMessage({ type: 'selectNode', id: node.id }));
    viewport.append(group);
  }

  lastLayout = state.graph;
  const shape = `${state.scopeKey}|${state.graph.nodes.length}|${Math.round(state.graph.width)}x${Math.round(state.graph.height)}`;
  const reshaped = shape !== lastShape;
  lastShape = shape;
  if (applyFocus(state.graph)) return;
  if (reshaped) userAdjusted = false;
  if (!userAdjusted) fitToView();
  else applyTransform();
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

let following = true;
let openDetailId: string | undefined;

function atBottom(element: HTMLElement, slack = 24): boolean {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= slack;
}

function scrollToLatest(): void {
  const body = byId('modal-body');
  body.scrollTop = body.scrollHeight;
  following = true;
  byId('jump').classList.add('hidden');
}

function renderDetail(detail: NodeDetail, refreshed: boolean): void {
  const body = byId('modal-body');
  const isSameNode = refreshed && openDetailId === detail.id;
  const keepScroll = isSameNode ? body.scrollTop : 0;
  if (!isSameNode) following = true;
  openDetailId = detail.id;

  byId('modal-title').textContent = detail.sublabel ? `${detail.label} — ${detail.sublabel}` : detail.label;

  const open = new Set<number>();
  const revealed = new Set<string>();
  if (isSameNode) {
    body.querySelectorAll('details[open]').forEach((node) => {
      const index = Number((node as HTMLElement).dataset['index']);
      if (!Number.isNaN(index)) open.add(index);
    });
    body.querySelectorAll('[data-revealed="true"]').forEach((node) => {
      const key = (node as HTMLElement).dataset['panel'];
      if (key) revealed.add(key);
    });
  }

  body.replaceChildren();
  if (detail.events.length === 0) {
    body.append(el('p', undefined, 'No recorded activity for this node.'));
  }
  detail.events.forEach((event, index) => body.append(renderEvent(event, index, open, revealed)));

  byId('overlay').classList.remove('hidden');
  if (following) scrollToLatest();
  else {
    body.scrollTop = keepScroll;
    byId('jump').classList.toggle('hidden', atBottom(body));
  }
}

function closeDetail(): void {
  byId('overlay').classList.add('hidden');
  openDetailId = undefined;
  following = true;
  vscode.postMessage({ type: 'closeDetail' });
}

const SPEAKER_LABEL: Record<SpeakerRole, string> = {
  user: 'you',
  assistant: 'said',
  meta: 'context',
};

function renderEvent(
  event: AgentEvent,
  index: number,
  open: ReadonlySet<number>,
  revealed: ReadonlySet<string>,
): HTMLElement {
  const speaker: SpeakerRole = event.role ?? 'assistant';
  const classes = ['event', event.kind];
  if (event.kind === 'text') classes.push(speaker);
  if (event.isError) classes.push('err');

  const wrapper = el('div', classes.join(' '));
  const head = el('div', 'head');

  if (event.kind === 'tool') {
    head.append(el('span', 'tool', event.name ?? 'tool'));
    if (event.summary) head.append(el('span', 'summary', event.summary));
  } else if (event.kind === 'thinking') {
    head.append(el('span', 'tool', 'thought'));
    if (!event.text) head.append(el('span', 'summary muted', 'not recorded'));
  } else {
    head.append(el('span', 'tool', SPEAKER_LABEL[speaker]));
  }
  wrapper.append(head);

  const panels: { label: string; body: string; openByDefault?: boolean }[] = [];
  if (event.kind === 'tool') {
    if (event.detail) panels.push({ label: 'arguments', body: event.detail });
    if (event.result) {
      panels.push({ label: event.isError ? 'error output' : 'output', body: event.result });
    }
  } else if (event.text) {
    const conversational = event.kind === 'thinking' || speaker !== 'meta';
    panels.push({ label: 'text', body: event.text, openByDefault: conversational });
  }

  for (const panel of panels) {
    const key = `${index}:${panel.label}`;
    const details = el('details');
    details.dataset['index'] = String(index);
    details.dataset['panel'] = key;
    const summary = el('summary', undefined, `${panel.label} · ${lineCount(panel.body)}`);
    const pre = el('pre');
    details.append(summary, pre);

    const preview = panel.openByDefault === true ? previewOf(panel.body) : undefined;
    const clipped = preview?.clipped === true ? preview : undefined;
    const more = clipped ? el('button', 'more') : undefined;
    let expanded = revealed.has(key);

    const paint = (): void => {
      pre.textContent = clipped && !expanded ? clipped.head : panel.body;
      if (!clipped || !more) return;
      more.textContent = expanded ? 'Show less' : moreLabel(clipped);
      details.dataset['revealed'] = expanded ? 'true' : 'false';
    };

    let filled = false;
    const fill = (): void => {
      if (filled) return;
      filled = true;
      paint();
    };

    if (more) {
      more.addEventListener('click', () => {
        expanded = !expanded;
        paint();
      });
      details.append(more);
    }

    details.open = open.has(index) || panel.openByDefault === true;
    if (details.open) fill();
    details.addEventListener('toggle', fill);

    wrapper.append(details);
  }
  return wrapper;
}

function lineCount(body: string): string {
  const lines = body.split('\n').length;
  return lines === 1 ? `${body.length} chars` : `${lines} lines`;
}

function wire(): void {
  wireViewport();
  byId('modal-close').addEventListener('click', () => closeDetail());
  byId('overlay').addEventListener('click', (event) => {
    if (event.target === byId('overlay')) closeDetail();
  });
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !byId('overlay').classList.contains('hidden')) closeDetail();
  });
  byId('jump').addEventListener('click', () => scrollToLatest());
  byId('modal-body').addEventListener('scroll', () => {
    const body = byId('modal-body');
    following = atBottom(body);
    byId('jump').classList.toggle('hidden', following);
  });

  window.addEventListener('message', (event: MessageEvent<HostMessage>) => {
    const message = event.data;
    try {
      if (message.type === 'state') {
        zoomSensitivity = message.state.zoomSensitivity;
        renderScope(message.state);
        renderStatus(message.state);
        renderGraph(message.state);
      } else if (message.type === 'detail') {
        renderDetail(message.detail, message.refreshed);
      } else if (message.type === 'detailClosed') {
        byId('overlay').classList.add('hidden');
        openDetailId = undefined;
      }
    } catch (error) {
      const text = document.getElementById('status-text');
      if (text) text.textContent = `render failed: ${error instanceof Error ? error.message : String(error)}`;
      throw error;
    }
  });

  vscode.postMessage({ type: 'ready' });
}

wire();
