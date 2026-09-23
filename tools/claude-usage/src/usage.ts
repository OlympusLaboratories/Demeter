import { Meter, MeterGroup, toSeverity } from './format';

export const USAGE_URL = 'https://api.anthropic.com/api/oauth/usage';
export const OAUTH_BETA = 'oauth-2025-04-20';

export interface UsageSnapshot {
  meters: Meter[];
  fetchedAt: number;
}

export type UsageFailureKind = 'unauthorized' | 'rateLimited' | 'server' | 'network' | 'malformed';

export interface UsageFailure {
  ok: false;
  kind: UsageFailureKind;
  status?: number;
  retryAfterMs?: number;
  message: string;
}

export type UsageResult = { ok: true; snapshot: UsageSnapshot } | UsageFailure;

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : undefined;
}

function asPercent(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : undefined;
}

function asResetsAt(value: unknown): number | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? undefined : parsed;
}

function scopeLabel(scope: unknown): string | undefined {
  const model = asRecord(asRecord(scope)?.['model']);
  const name = model?.['display_name'] ?? model?.['id'];
  return typeof name === 'string' && name.length > 0 ? name : undefined;
}

function formatMoney(entry: unknown): string | undefined {
  const record = asRecord(entry);
  const minor = record?.['amount_minor'];
  if (typeof minor !== 'number') {
    return undefined;
  }
  const exponent = typeof record?.['exponent'] === 'number' ? (record['exponent'] as number) : 2;
  const currency = typeof record?.['currency'] === 'string' ? (record['currency'] as string) : 'USD';
  const amount = minor / 10 ** exponent;
  try {
    return amount.toLocaleString(undefined, { style: 'currency', currency });
  } catch {
    return `${amount.toFixed(exponent)} ${currency}`;
  }
}

function legacyMeter(
  raw: Record<string, unknown>,
  key: string,
  group: MeterGroup,
  label: string,
  shortLabel: string,
  title: string,
): Meter | undefined {
  const entry = asRecord(raw[key]);
  const percent = asPercent(entry?.['utilization']);
  if (entry === undefined || percent === undefined) {
    return undefined;
  }
  return {
    id: group === 'scoped' ? `scoped:${label}` : group,
    group,
    label,
    shortLabel,
    title,
    percent,
    severity: 'normal',
    resetsAt: asResetsAt(entry['resets_at']),
  };
}

function spendMeter(raw: Record<string, unknown>): Meter | undefined {
  const spend = asRecord(raw['spend']);
  if (spend === undefined || spend['enabled'] !== true) {
    return undefined;
  }
  const percent = asPercent(spend['percent']);
  if (percent === undefined) {
    return undefined;
  }
  const used = formatMoney(spend['used']);
  const limit = formatMoney(spend['limit']);
  return {
    id: 'spend',
    group: 'spend',
    label: 'Credits',
    shortLabel: '$',
    title: 'Extra usage credits',
    percent,
    severity: toSeverity(spend['severity']),
    detail: used && limit ? `${used} of ${limit}` : used,
  };
}

export function parseUsage(raw: unknown, fetchedAt: number): UsageSnapshot | undefined {
  const body = asRecord(raw);
  if (body === undefined) {
    return undefined;
  }
  const meters: Meter[] = [];
  const limits = body['limits'];

  if (Array.isArray(limits)) {
    let scopedIndex = 0;
    for (const item of limits) {
      const entry = asRecord(item);
      const percent = asPercent(entry?.['percent']);
      if (entry === undefined || percent === undefined) {
        continue;
      }
      const kind = typeof entry['kind'] === 'string' ? (entry['kind'] as string) : '';
      const severity = toSeverity(entry['severity']);
      const resetsAt = asResetsAt(entry['resets_at']);
      if (kind === 'session') {
        meters.push({
          id: 'session',
          group: 'session',
          label: 'Session',
          shortLabel: '5h',
          title: 'Current session (5 hours)',
          percent,
          severity,
          resetsAt,
        });
      } else if (kind === 'weekly_all') {
        meters.push({
          id: 'weekly',
          group: 'weekly',
          label: 'Weekly',
          shortLabel: '7d',
          title: 'Current week (all models)',
          percent,
          severity,
          resetsAt,
        });
      } else if (kind === 'weekly_scoped') {
        const name = scopeLabel(entry['scope']) ?? `scoped${scopedIndex}`;
        scopedIndex += 1;
        meters.push({
          id: `scoped:${name}`,
          group: 'scoped',
          label: name,
          shortLabel: name,
          title: `Current week (${name})`,
          percent,
          severity,
          resetsAt,
        });
      }
    }
  }

  if (meters.length === 0) {
    const session = legacyMeter(body, 'five_hour', 'session', 'Session', '5h', 'Current session (5 hours)');
    const weekly = legacyMeter(body, 'seven_day', 'weekly', 'Weekly', '7d', 'Current week (all models)');
    const opus = legacyMeter(body, 'seven_day_opus', 'scoped', 'Opus', 'Opus', 'Current week (Opus)');
    for (const meter of [session, weekly, opus]) {
      if (meter) {
        meters.push(meter);
      }
    }
  }

  const spend = spendMeter(body);
  if (spend) {
    meters.push(spend);
  }

  if (meters.length === 0) {
    return undefined;
  }
  return { meters, fetchedAt };
}

function retryAfterMs(header: string | null): number | undefined {
  if (!header) {
    return undefined;
  }
  const seconds = Number(header);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return seconds * 1000;
  }
  const date = Date.parse(header);
  return Number.isNaN(date) ? undefined : Math.max(0, date - Date.now());
}

export async function fetchUsage(accessToken: string, signal?: AbortSignal): Promise<UsageResult> {
  let response: Response;
  try {
    response = await fetch(USAGE_URL, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'anthropic-beta': OAUTH_BETA,
        Accept: 'application/json',
      },
      signal,
    });
  } catch (error) {
    return { ok: false, kind: 'network', message: error instanceof Error ? error.message : String(error) };
  }

  if (response.status === 401 || response.status === 403) {
    return { ok: false, kind: 'unauthorized', status: response.status, message: 'Token rejected' };
  }
  if (response.status === 429) {
    return {
      ok: false,
      kind: 'rateLimited',
      status: 429,
      retryAfterMs: retryAfterMs(response.headers.get('retry-after')),
      message: 'Rate limited by the usage endpoint',
    };
  }
  if (!response.ok) {
    return { ok: false, kind: 'server', status: response.status, message: `HTTP ${response.status}` };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    return { ok: false, kind: 'malformed', message: error instanceof Error ? error.message : String(error) };
  }

  const snapshot = parseUsage(body, Date.now());
  if (snapshot === undefined) {
    return { ok: false, kind: 'malformed', message: 'No recognisable limits in the response' };
  }
  return { ok: true, snapshot };
}
