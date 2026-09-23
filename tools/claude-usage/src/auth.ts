import * as crypto from 'node:crypto';
import * as vscode from 'vscode';
import { ClaudeCodeToken, isUsable, readClaudeCodeToken } from './claudeCodeCreds';
import { Logger } from './log';
import {
  MANUAL_REDIRECT_URL,
  OAuthTokens,
  authorizeUrl,
  createPkce,
  exchangeCode,
  refreshTokens,
  splitManualCode,
  startLoopbackListener,
} from './oauth';

export type CredentialMode = 'auto' | 'claudeCode' | 'browser';
export type TokenSource = 'claudeCode' | 'browser';

export interface ResolvedToken {
  accessToken: string;
  source: TokenSource;
}

const SECRET_KEY = 'claudeUsage.browserTokens';
const REFRESH_SKEW_MS = 2 * 60_000;
const SIGN_IN_TIMEOUT_MS = 5 * 60_000;

function fingerprint(token: string): string {
  return crypto.createHash('sha256').update(token).digest('hex').slice(0, 16);
}

export class AuthManager {
  private readonly rejected = new Set<string>();
  private cachedBrowserTokens: OAuthTokens | undefined;
  private loaded = false;
  private signInInFlight: Promise<boolean> | undefined;

  constructor(
    private readonly secrets: vscode.SecretStorage,
    private readonly logger: Logger,
  ) {}

  async resolve(mode: CredentialMode): Promise<ResolvedToken | undefined> {
    if (mode !== 'browser') {
      const token = await this.claudeCodeToken();
      if (token) {
        return { accessToken: token, source: 'claudeCode' };
      }
    }
    if (mode === 'claudeCode') {
      return undefined;
    }
    const browser = await this.browserToken();
    return browser ? { accessToken: browser, source: 'browser' } : undefined;
  }

  async hasBrowserLogin(): Promise<boolean> {
    await this.load();
    return this.cachedBrowserTokens !== undefined;
  }

  private async claudeCodeToken(): Promise<string | undefined> {
    let stored: ClaudeCodeToken | undefined;
    try {
      stored = await readClaudeCodeToken();
    } catch (error) {
      this.logger.info(`Could not read the Claude Code credentials: ${String(error)}`);
      return undefined;
    }
    if (!isUsable(stored, Date.now())) {
      return undefined;
    }
    const accessToken = stored!.accessToken;
    if (this.rejected.has(fingerprint(accessToken))) {
      return undefined;
    }
    return accessToken;
  }

  private async browserToken(): Promise<string | undefined> {
    await this.load();
    const tokens = this.cachedBrowserTokens;
    if (tokens === undefined) {
      return undefined;
    }
    const expired = tokens.expiresAt !== undefined && tokens.expiresAt - REFRESH_SKEW_MS <= Date.now();
    if (!expired && !this.rejected.has(fingerprint(tokens.accessToken))) {
      return tokens.accessToken;
    }
    if (tokens.refreshToken === undefined) {
      return undefined;
    }
    try {
      this.logger.info('Refreshing the browser login token.');
      const next = await refreshTokens(tokens.refreshToken);
      await this.store({ ...next, refreshToken: next.refreshToken ?? tokens.refreshToken });
      return this.cachedBrowserTokens?.accessToken;
    } catch (error) {
      this.logger.info(`Refresh failed, the browser login needs redoing: ${String(error)}`);
      await this.store(undefined);
      return undefined;
    }
  }

  async reject(source: TokenSource, accessToken: string): Promise<void> {
    this.rejected.add(fingerprint(accessToken));
    this.logger.info(`The ${source} token was rejected; it will be skipped until it changes.`);
    if (source === 'browser') {
      await this.browserToken();
    }
  }

  signIn(): Promise<boolean> {
    this.signInInFlight ??= this.runSignIn().finally(() => {
      this.signInInFlight = undefined;
    });
    return this.signInInFlight;
  }

  private async runSignIn(): Promise<boolean> {
    try {
      const tokens = await this.loopbackSignIn();
      if (tokens) {
        await this.store(tokens);
        return true;
      }
    } catch (error) {
      this.logger.info(`Browser sign-in did not complete: ${String(error)}`);
    }
    const retry = await vscode.window.showWarningMessage(
      'Claude Usage did not receive the sign-in redirect. Paste the authorization code instead?',
      'Paste Code',
      'Cancel',
    );
    if (retry !== 'Paste Code') {
      return false;
    }
    try {
      const tokens = await this.manualSignIn();
      if (tokens) {
        await this.store(tokens);
        return true;
      }
    } catch (error) {
      this.logger.info(`Manual sign-in failed: ${String(error)}`);
      void vscode.window.showErrorMessage(`Claude Usage sign-in failed: ${String(error)}`);
    }
    return false;
  }

  private async loopbackSignIn(): Promise<OAuthTokens | undefined> {
    const pkce = createPkce();
    const listener = await startLoopbackListener(pkce);
    try {
      const opened = await vscode.env.openExternal(vscode.Uri.parse(authorizeUrl(pkce, listener.redirectUri)));
      if (!opened) {
        throw new Error('The browser could not be opened');
      }
      const code = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Claude Usage: finish signing in the browser', cancellable: true },
        (_progress, cancellation) =>
          Promise.race([
            listener.waitForCode(),
            new Promise<undefined>((resolve) => {
              cancellation.onCancellationRequested(() => resolve(undefined));
              setTimeout(() => resolve(undefined), SIGN_IN_TIMEOUT_MS);
            }),
          ]),
      );
      if (code === undefined) {
        return undefined;
      }
      return await exchangeCode({
        code,
        verifier: pkce.verifier,
        state: pkce.state,
        redirectUri: listener.redirectUri,
      });
    } finally {
      listener.dispose();
    }
  }

  private async manualSignIn(): Promise<OAuthTokens | undefined> {
    const pkce = createPkce();
    const opened = await vscode.env.openExternal(vscode.Uri.parse(authorizeUrl(pkce, MANUAL_REDIRECT_URL)));
    if (!opened) {
      throw new Error('The browser could not be opened');
    }
    const pasted = await vscode.window.showInputBox({
      title: 'Claude Usage sign-in',
      prompt: 'Paste the authorization code shown in the browser',
      ignoreFocusOut: true,
      password: true,
    });
    if (pasted === undefined || pasted.trim().length === 0) {
      return undefined;
    }
    const { code, state } = splitManualCode(pasted);
    return exchangeCode({
      code,
      verifier: pkce.verifier,
      state: state ?? pkce.state,
      redirectUri: MANUAL_REDIRECT_URL,
    });
  }

  async signOut(): Promise<void> {
    await this.store(undefined);
    this.rejected.clear();
  }

  private async load(): Promise<void> {
    if (this.loaded) {
      return;
    }
    this.loaded = true;
    const raw = await this.secrets.get(SECRET_KEY);
    if (raw === undefined) {
      return;
    }
    try {
      const parsed = JSON.parse(raw) as OAuthTokens;
      if (typeof parsed.accessToken === 'string' && parsed.accessToken.length > 0) {
        this.cachedBrowserTokens = parsed;
      }
    } catch {
      this.cachedBrowserTokens = undefined;
    }
  }

  private async store(tokens: OAuthTokens | undefined): Promise<void> {
    this.loaded = true;
    this.cachedBrowserTokens = tokens;
    if (tokens === undefined) {
      await this.secrets.delete(SECRET_KEY);
      return;
    }
    this.rejected.delete(fingerprint(tokens.accessToken));
    await this.secrets.store(SECRET_KEY, JSON.stringify(tokens));
  }
}
