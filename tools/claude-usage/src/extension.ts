import * as vscode from 'vscode';
import { AuthManager, CredentialMode, ResolvedToken } from './auth';
import {
  AgeMode,
  BAR_STYLES,
  BarStyle,
  LabelStyle,
  Meter,
  MeterGroup,
  RenderOptions,
  Severity,
  formatAge,
  formatPercent,
  formatRemaining,
  formatResetClock,
  freshness,
  meterSeverity,
  meterText,
  renderBar,
} from './format';
import { Logger } from './log';
import { CacheRecord, UsageCache } from './cache';
import { UsageFailure, UsageSnapshot, fetchUsage } from './usage';

const GROUP_ORDER: MeterGroup[] = ['session', 'weekly', 'scoped', 'spend'];
const MIN_BACKOFF_MS = 60_000;
const MAX_BACKOFF_MS = 15 * 60_000;
const LOCK_STALE_MS = 60_000;
const FRESH_FRACTION = 0.9;

interface Settings {
  enabled: boolean;
  pollMs: number;
  credentials: CredentialMode;
  show: MeterGroup[];
  alignment: vscode.StatusBarAlignment;
  priority: number;
  age: AgeMode;
  render: RenderOptions;
}

function readSettings(): Settings {
  const config = vscode.workspace.getConfiguration('claudeUsage');
  const show = config.get<string[]>('show', ['session', 'weekly']);
  return {
    enabled: config.get<boolean>('enabled', true),
    pollMs: Math.max(15, config.get<number>('pollSeconds', 60)) * 1000,
    credentials: config.get<CredentialMode>('credentials', 'auto'),
    show: GROUP_ORDER.filter((group) => show.includes(group)),
    alignment:
      config.get<string>('alignment', 'right') === 'left'
        ? vscode.StatusBarAlignment.Left
        : vscode.StatusBarAlignment.Right,
    priority: config.get<number>('priority', 100),
    age: config.get<AgeMode>('age', 'always'),
    render: {
      labelStyle: config.get<LabelStyle>('labelStyle', 'long'),
      barWidth: config.get<number>('barWidth', 6),
      barStyle: config.get<BarStyle>('barStyle', 'dots'),
      showReset: config.get<boolean>('showReset', true),
      warnAtPercent: config.get<number>('warnAtPercent', 75),
      criticalAtPercent: config.get<number>('criticalAtPercent', 90),
    },
  };
}

function severityColor(severity: Severity): vscode.ThemeColor | undefined {
  if (severity === 'critical') {
    return new vscode.ThemeColor('charts.red');
  }
  if (severity === 'warning') {
    return new vscode.ThemeColor('charts.yellow');
  }
  return undefined;
}

class UsageController {
  private readonly items = new Map<string, vscode.StatusBarItem>();
  private readonly noticeItem: vscode.StatusBarItem;
  private readonly freshnessItem: vscode.StatusBarItem;
  private settings = readSettings();
  private snapshot: UsageSnapshot | undefined;
  private notice: string | undefined;
  private needsSignIn = false;
  private backoffMs = 0;
  private retryUntil: number | undefined;
  private timer: NodeJS.Timeout | undefined;
  private clock: NodeJS.Timeout | undefined;
  private inFlight = false;
  private lastSource: ResolvedToken['source'] | undefined;
  private adoptedAt = 0;
  private stylePreview: BarStyle | undefined;
  private updatedAt: number | undefined;
  private cacheWatch: { dispose(): void } | undefined;

  constructor(
    private readonly auth: AuthManager,
    private readonly logger: Logger,
    private readonly cache: UsageCache,
  ) {
    this.noticeItem = vscode.window.createStatusBarItem(this.settings.alignment, this.settings.priority);
    this.freshnessItem = vscode.window.createStatusBarItem(this.settings.alignment, this.settings.priority - 50);
    this.freshnessItem.command = 'claudeUsage.refresh';
  }

  start(): void {
    this.applySettings();
    this.cacheWatch = this.cache.watch(() => void this.onCacheChanged());
    void this.poll('startup');
  }

  applySettings(): void {
    const next = readSettings();
    const alignmentChanged = next.alignment !== this.settings.alignment || next.priority !== this.settings.priority;
    this.settings = next;
    if (alignmentChanged) {
      this.disposeItems();
    }
    this.render();
    this.schedule();
  }

  private schedule(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
    if (this.clock) {
      clearInterval(this.clock);
      this.clock = undefined;
    }
    if (!this.settings.enabled) {
      return;
    }
    const base = Math.max(this.settings.pollMs, this.backoffMs);
    const delay = base + Math.floor(Math.random() * Math.min(5_000, base * 0.1));
    this.timer = setTimeout(() => void this.poll('timer'), delay);
    this.clock = setInterval(() => this.render(), 10_000);
  }

  async refreshNow(): Promise<void> {
    this.backoffMs = 0;
    await this.poll('manual');
  }

  onFocusChanged(focused: boolean): void {
    if (focused && this.settings.enabled) {
      void this.poll('focus');
    }
  }

  private async poll(reason: string): Promise<void> {
    if (!this.settings.enabled || this.inFlight) {
      return;
    }
    if (reason === 'timer' && !vscode.window.state.focused) {
      this.schedule();
      return;
    }
    this.inFlight = true;
    try {
      const cached = await this.cache.read();
      if (cached && this.canReuse(cached, reason)) {
        this.adopt(cached);
        return;
      }

      const ran = await this.cache.withLock(LOCK_STALE_MS, async () => {
        const token = await this.auth.resolve(this.settings.credentials);
        if (token === undefined) {
          await this.handleMissingToken();
          return;
        }
        this.lastSource = token.source;
        const result = await fetchUsage(token.accessToken);
        if (result.ok) {
          this.snapshot = result.snapshot;
          this.notice = undefined;
          this.needsSignIn = false;
          this.backoffMs = 0;
          this.retryUntil = undefined;
          this.updatedAt = result.snapshot.fetchedAt;
          this.logger.info(
            `Usage refreshed via ${token.source} (${reason}): ${result.snapshot.meters
              .map((meter) => `${meter.label} ${formatPercent(meter.percent)}`)
              .join(', ')}`,
          );
        } else {
          await this.handleFailure(result, token);
        }
        await this.publish();
      });

      if (ran === undefined) {
        this.logger.info(`Another window is fetching (${reason}); using the shared reading.`);
        const shared = await this.cache.read();
        if (shared) {
          this.adopt(shared);
        }
      }
    } finally {
      this.inFlight = false;
      this.render();
      this.schedule();
    }
  }

  private canReuse(cached: CacheRecord, reason: string): boolean {
    const now = Date.now();
    if (cached.retryUntil !== undefined && now < cached.retryUntil) {
      return true;
    }
    if (reason === 'manual') {
      return false;
    }
    return cached.snapshot !== undefined && now - cached.updatedAt < this.settings.pollMs * FRESH_FRACTION;
  }

  private adopt(cached: CacheRecord): void {
    this.snapshot = cached.snapshot;
    this.notice = cached.notice;
    this.needsSignIn = cached.notice !== undefined && cached.snapshot === undefined && this.settings.credentials !== 'claudeCode';
    if (cached.source === 'browser' || cached.source === 'claudeCode') {
      this.lastSource = cached.source;
    }
    this.updatedAt = cached.snapshot?.fetchedAt ?? cached.updatedAt;
    this.retryUntil = cached.retryUntil;
    if (cached.retryUntil !== undefined) {
      this.backoffMs = Math.max(0, cached.retryUntil - Date.now());
    }
  }

  private async publish(): Promise<void> {
    await this.cache.write({
      updatedAt: Date.now(),
      snapshot: this.snapshot,
      source: this.lastSource,
      notice: this.notice,
      retryUntil: this.retryUntil,
    });
  }

  private async onCacheChanged(): Promise<void> {
    if (this.inFlight) {
      return;
    }
    const cached = await this.cache.read();
    if (cached === undefined || cached.updatedAt <= this.adoptedAt) {
      return;
    }
    this.adoptedAt = cached.updatedAt;
    this.adopt(cached);
    this.render();
  }

  private async handleMissingToken(): Promise<void> {
    this.snapshot = undefined;
    if (this.settings.credentials === 'claudeCode') {
      this.notice = 'No usable Claude Code login found. Open Claude Code and sign in there.';
      this.needsSignIn = false;
    } else {
      this.notice = 'Sign in to show Claude usage.';
      this.needsSignIn = true;
    }
    this.applyBackoff();
    this.logger.info(this.notice);
  }

  private applyBackoff(explicitMs?: number): void {
    this.backoffMs = Math.min(
      MAX_BACKOFF_MS,
      explicitMs ?? Math.max(MIN_BACKOFF_MS, this.backoffMs * 2 || MIN_BACKOFF_MS),
    );
    this.retryUntil = Date.now() + this.backoffMs;
  }

  private async handleFailure(failure: UsageFailure, token: ResolvedToken): Promise<void> {
    this.logger.info(`Usage request failed (${failure.kind}): ${failure.message}`);
    if (failure.kind === 'unauthorized') {
      await this.auth.reject(token.source, token.accessToken);
      this.backoffMs = 0;
      this.retryUntil = undefined;
      this.notice =
        token.source === 'claudeCode'
          ? 'The Claude Code token was rejected. It refreshes the next time you use Claude Code.'
          : 'The browser login expired. Sign in again.';
      this.needsSignIn = this.settings.credentials !== 'claudeCode';
      return;
    }
    if (failure.kind === 'rateLimited') {
      this.applyBackoff(failure.retryAfterMs);
      this.notice = 'Rate limited; backing off.';
      return;
    }
    this.applyBackoff();
    this.notice = failure.message;
  }

  private renderOptions(): RenderOptions {
    return this.stylePreview === undefined
      ? this.settings.render
      : { ...this.settings.render, barStyle: this.stylePreview };
  }

  previewBarStyle(style: BarStyle | undefined): void {
    this.stylePreview = style;
    this.render();
  }

  sampleMeterPercent(): number {
    return this.snapshot?.meters[0]?.percent ?? 35;
  }

  private visibleMeters(): Meter[] {
    if (this.snapshot === undefined) {
      return [];
    }
    return this.snapshot.meters.filter((meter) => this.settings.show.includes(meter.group));
  }

  private render(): void {
    if (!this.settings.enabled) {
      this.disposeItems();
      this.freshnessItem.hide();
      this.noticeItem.hide();
      return;
    }
    const now = Date.now();
    const meters = this.visibleMeters();
    const seen = new Set<string>();

    meters.forEach((meter, index) => {
      seen.add(meter.id);
      let item = this.items.get(meter.id);
      if (item === undefined) {
        item = vscode.window.createStatusBarItem(this.settings.alignment, this.settings.priority - index);
        item.command = 'claudeUsage.refresh';
        this.items.set(meter.id, item);
      }
      item.text = meterText(meter, this.renderOptions(), now);
      item.color = severityColor(meterSeverity(meter, this.renderOptions()));
      item.tooltip = this.tooltip(now);
      item.show();
    });

    for (const [id, item] of this.items) {
      if (!seen.has(id)) {
        item.dispose();
        this.items.delete(id);
      }
    }

    const chip = freshness({
      updatedAt: this.updatedAt,
      retryUntil: this.retryUntil,
      now,
      pollMs: this.settings.pollMs,
      mode: this.settings.age,
    });
    if (chip && (meters.length > 0 || this.snapshot !== undefined)) {
      this.freshnessItem.text = chip.text;
      this.freshnessItem.color = severityColor(chip.severity);
      this.freshnessItem.tooltip = this.tooltip(now);
      this.freshnessItem.show();
    } else {
      this.freshnessItem.hide();
    }

    if (meters.length === 0 && this.notice !== undefined) {
      this.noticeItem.text = this.needsSignIn ? '$(sign-in) Claude usage' : '$(warning) Claude usage';
      this.noticeItem.command = this.needsSignIn ? 'claudeUsage.signIn' : 'claudeUsage.refresh';
      this.noticeItem.tooltip = this.tooltip(now);
      this.noticeItem.show();
    } else {
      this.noticeItem.hide();
    }
  }

  private tooltip(now: number): vscode.MarkdownString {
    const md = new vscode.MarkdownString();
    md.isTrusted = true;
    md.supportThemeIcons = true;

    if (this.snapshot) {
      md.appendMarkdown('**Claude usage**\n\n');
      for (const meter of this.snapshot.meters) {
        md.appendMarkdown(`- ${meter.title}: **${formatPercent(meter.percent)}**`);
        if (meter.detail) {
          md.appendMarkdown(` (${meter.detail})`);
        }
        if (meter.resetsAt !== undefined) {
          md.appendMarkdown(` — resets in ${formatRemaining(meter.resetsAt - now)}, at ${formatResetClock(meter.resetsAt, now)}`);
        }
        md.appendMarkdown('\n');
      }
      const age = now - this.snapshot.fetchedAt;
      md.appendMarkdown(`\nUpdated ${age < 15_000 ? 'just now' : `${formatAge(age)} ago`}`);
      if (this.retryUntil !== undefined && this.retryUntil > now) {
        md.appendMarkdown(` · backing off, next try in ${formatRemaining(this.retryUntil - now)}`);
      }
      md.appendMarkdown(` · source: ${this.lastSource === 'browser' ? 'browser login' : 'Claude Code login'}\n`);
    }

    if (this.notice) {
      md.appendMarkdown(`\n$(warning) ${this.notice}\n`);
    }

    md.appendMarkdown('\n[Refresh](command:claudeUsage.refresh)');
    if (this.needsSignIn) {
      md.appendMarkdown(' · [Sign in](command:claudeUsage.signIn)');
    }
    md.appendMarkdown(' · [Log](command:claudeUsage.showDetails)');
    return md;
  }

  private disposeItems(): void {
    for (const item of this.items.values()) {
      item.dispose();
    }
    this.items.clear();
  }

  dispose(): void {
    if (this.timer) {
      clearTimeout(this.timer);
    }
    if (this.clock) {
      clearInterval(this.clock);
    }
    this.cacheWatch?.dispose();
    this.disposeItems();
    this.freshnessItem.dispose();
    this.noticeItem.dispose();
  }
}


interface BarStyleItem extends vscode.QuickPickItem {
  style: BarStyle;
}

async function pickBarStyle(controller: UsageController): Promise<void> {
  const config = vscode.workspace.getConfiguration('claudeUsage');
  const original = config.get<BarStyle>('barStyle', 'dots');
  const width = config.get<number>('barWidth', 6);
  const percent = controller.sampleMeterPercent();

  const quickPick = vscode.window.createQuickPick<BarStyleItem>();
  quickPick.title = 'Claude Usage: bar style';
  quickPick.placeholder = 'Move through the list to preview it in the status bar, then press Enter';
  quickPick.items = BAR_STYLES.map((style) => ({
    label: `${renderBar(percent, width, style)}  ${style}`,
    description: style === original ? 'current' : undefined,
    style,
  }));
  const current = quickPick.items.find((item) => item.style === original);
  if (current) {
    quickPick.activeItems = [current];
  }

  let chosen: BarStyle | undefined;
  quickPick.onDidChangeActive((active) => {
    const item = active[0];
    if (item) {
      controller.previewBarStyle(item.style);
    }
  });
  quickPick.onDidAccept(() => {
    chosen = quickPick.activeItems[0]?.style;
    quickPick.hide();
  });
  quickPick.onDidHide(() => {
    controller.previewBarStyle(undefined);
    quickPick.dispose();
    if (chosen !== undefined && chosen !== original) {
      void config.update('barStyle', chosen, vscode.ConfigurationTarget.Global);
    }
  });
  quickPick.show();
}

export function activate(context: vscode.ExtensionContext): void {
  const logger = new Logger();
  const auth = new AuthManager(context.secrets, logger);
  const controller = new UsageController(auth, logger, new UsageCache());

  context.subscriptions.push(
    logger,
    controller,
    vscode.commands.registerCommand('claudeUsage.refresh', () => controller.refreshNow()),
    vscode.commands.registerCommand('claudeUsage.signIn', async () => {
      if (await auth.signIn()) {
        await controller.refreshNow();
      }
    }),
    vscode.commands.registerCommand('claudeUsage.signOut', async () => {
      await auth.signOut();
      await controller.refreshNow();
      void vscode.window.showInformationMessage('Claude Usage forgot its browser login.');
    }),
    vscode.commands.registerCommand('claudeUsage.showDetails', () => logger.show()),
    vscode.commands.registerCommand('claudeUsage.pickBarStyle', () => pickBarStyle(controller)),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration('claudeUsage')) {
        controller.applySettings();
      }
    }),
    vscode.window.onDidChangeWindowState((state) => controller.onFocusChanged(state.focused)),
  );

  controller.start();
}

export function deactivate(): void {}
