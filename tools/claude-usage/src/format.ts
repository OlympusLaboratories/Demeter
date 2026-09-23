export type Severity = 'normal' | 'warning' | 'critical';

export type MeterGroup = 'session' | 'weekly' | 'scoped' | 'spend';

export interface Meter {
  id: string;
  group: MeterGroup;
  label: string;
  shortLabel: string;
  title: string;
  percent: number;
  severity: Severity;
  resetsAt?: number;
  detail?: string;
}

export type BarStyle = 'dots' | 'squares' | 'bars' | 'blocks' | 'shaded' | 'line' | 'ascii';

export type LabelStyle = 'long' | 'short';

export type AgeMode = 'always' | 'whenStale' | 'never';

export interface RenderOptions {
  labelStyle: LabelStyle;
  barWidth: number;
  barStyle: BarStyle;
  showReset: boolean;
  warnAtPercent: number;
  criticalAtPercent: number;
}

const BAR_GLYPHS: Record<BarStyle, [string, string]> = {
  dots: ['●', '○'],
  squares: ['■', '□'],
  bars: ['▮', '▯'],
  blocks: ['█', '░'],
  shaded: ['▰', '▱'],
  line: ['━', '─'],
  ascii: ['#', '-'],
};

export const BAR_STYLES = Object.keys(BAR_GLYPHS) as BarStyle[];

const SEVERITY_RANK: Record<Severity, number> = { normal: 0, warning: 1, critical: 2 };

export function toSeverity(value: unknown): Severity {
  return value === 'warning' || value === 'critical' ? value : 'normal';
}

export function escalate(base: Severity, percent: number, warnAt: number, criticalAt: number): Severity {
  const byThreshold: Severity =
    percent >= criticalAt ? 'critical' : percent >= warnAt ? 'warning' : 'normal';
  return SEVERITY_RANK[byThreshold] > SEVERITY_RANK[base] ? byThreshold : base;
}

export function worstSeverity(severities: Severity[]): Severity {
  return severities.reduce<Severity>(
    (worst, next) => (SEVERITY_RANK[next] > SEVERITY_RANK[worst] ? next : worst),
    'normal',
  );
}

export function renderBar(percent: number, width: number, style: BarStyle): string {
  if (width <= 0) {
    return '';
  }
  const [full, empty] = BAR_GLYPHS[style] ?? BAR_GLYPHS.dots;
  const clamped = Math.max(0, Math.min(100, percent));
  let filled = Math.round((clamped / 100) * width);
  if (clamped > 0 && filled === 0) {
    filled = 1;
  }
  if (clamped < 100 && filled === width) {
    filled = width - 1;
  }
  return full.repeat(filled) + empty.repeat(width - filled);
}

export function formatRemaining(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) {
    return 'now';
  }
  const totalMinutes = Math.floor(ms / 60_000);
  if (totalMinutes < 1) {
    return '<1m';
  }
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) {
    return hours > 0 ? `${days}d${hours}h` : `${days}d`;
  }
  if (hours > 0) {
    return minutes > 0 ? `${hours}h${minutes}m` : `${hours}h`;
  }
  return `${minutes}m`;
}

export function formatPercent(percent: number): string {
  const clamped = Math.max(0, Math.min(100, percent));
  return `${Math.round(clamped)}%`;
}

export function meterText(meter: Meter, options: RenderOptions, now: number): string {
  const parts = [options.labelStyle === 'short' ? meter.shortLabel : meter.label];
  const bar = renderBar(meter.percent, options.barWidth, options.barStyle);
  if (bar) {
    parts.push(bar);
  }
  parts.push(formatPercent(meter.percent));
  if (options.showReset && meter.resetsAt !== undefined) {
    parts.push(formatRemaining(meter.resetsAt - now));
  }
  return parts.join(' ');
}

export function meterSeverity(meter: Meter, options: RenderOptions): Severity {
  return escalate(meter.severity, meter.percent, options.warnAtPercent, options.criticalAtPercent);
}

export function formatResetClock(resetsAt: number, now: number): string {
  const when = new Date(resetsAt);
  const sameDay = new Date(now).toDateString() === when.toDateString();
  const time = when.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  if (sameDay) {
    return time;
  }
  const day = when.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  return `${day} ${time}`;
}

export function formatAge(ms: number): string {
  if (!Number.isFinite(ms) || ms < 15_000) {
    return 'now';
  }
  if (ms < 60_000) {
    return `${Math.round(ms / 1000)}s`;
  }
  return formatRemaining(ms);
}

export interface Freshness {
  text: string;
  severity: Severity;
  stale: boolean;
}

export function freshness(options: {
  updatedAt?: number;
  retryUntil?: number;
  now: number;
  pollMs: number;
  mode: AgeMode;
}): Freshness | undefined {
  const { updatedAt, retryUntil, now, pollMs, mode } = options;
  if (mode === 'never') {
    return undefined;
  }
  const backingOff = retryUntil !== undefined && retryUntil > now;
  const age = updatedAt === undefined ? undefined : Math.max(0, now - updatedAt);
  const stale = age !== undefined && age > pollMs * 2.5;

  if (backingOff) {
    const retry = formatRemaining(retryUntil - now);
    return {
      text: age === undefined ? `$(warning) retry ${retry}` : `$(warning) ${formatAge(age)} · retry ${retry}`,
      severity: 'warning',
      stale: true,
    };
  }
  if (age === undefined) {
    return undefined;
  }
  if (stale) {
    return { text: `$(warning) ${formatAge(age)}`, severity: 'warning', stale: true };
  }
  if (mode === 'whenStale') {
    return undefined;
  }
  return { text: `$(history) ${formatAge(age)}`, severity: 'normal', stale: false };
}
