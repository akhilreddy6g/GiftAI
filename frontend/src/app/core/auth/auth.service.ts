import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { AuthError, Session } from '@supabase/auth-js';

import { AUTH_CLIENT } from './auth-client';
import { describeAuthError } from './auth-errors';

/** The outcome of an auth action: an error message for the user, or success. */
export type AuthResult = { ok: true } | { ok: false; message: string };

export type SignUpResult = AuthResult & { needsEmailConfirmation?: boolean };

const NOT_CONFIGURED =
  "Sign-in isn't set up for this copy of GiftAI. Set SUPABASE_URL and SUPABASE_ANON_KEY, then rebuild.";

/**
 * The signed-in session, kept in a signal, and every way to sign in or out. Supabase
 * stores the session in the browser and refreshes the token before it expires.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly client = inject(AUTH_CLIENT);
  private readonly router = inject(Router);

  /** Undefined until the stored session has been read. */
  private readonly sessionState = signal<Session | null | undefined>(undefined);

  readonly session = this.sessionState.asReadonly();
  readonly isConfigured = this.client !== null;
  readonly isSignedIn = computed(() => !!this.sessionState());
  readonly email = computed(() => this.sessionState()?.user.email ?? null);

  /** Resolves once the stored session, or one from a sign-in link, has been read. */
  readonly ready: Promise<void>;

  /** Runs whenever the user signs out, here or in another tab, so state can be cleared. */
  private readonly signOutListeners = new Set<() => void>();

  constructor() {
    const client = this.client;
    if (!client) {
      this.sessionState.set(null);
      this.ready = Promise.resolve();
      return;
    }
    client.onAuthStateChange((event, session) => {
      this.sessionState.set(session);
      if (event === 'SIGNED_OUT') {
        this.signOutListeners.forEach((listener) => listener());
      }
      if (event === 'PASSWORD_RECOVERY') {
        // Deferred: Supabase forbids auth calls inside this callback, and navigation
        // runs guards that read the session.
        setTimeout(() => void this.router.navigateByUrl('/reset-password'));
      }
    });
    this.ready = client.initialize().then(async () => {
      const { data } = await client.getSession();
      this.sessionState.set(data.session);
    });
  }

  onSignOut(listener: () => void): () => void {
    this.signOutListeners.add(listener);
    return () => this.signOutListeners.delete(listener);
  }

  /** A current access token for the API, refreshed first if it is about to expire. */
  async accessToken(): Promise<string | null> {
    if (!this.client) return null;
    await this.ready;
    const { data } = await this.client.getSession();
    return data.session?.access_token ?? null;
  }

  signInWithPassword(email: string, password: string): Promise<AuthResult> {
    return this.run((client) => client.signInWithPassword({ email, password }));
  }

  async signUp(email: string, password: string): Promise<SignUpResult> {
    const client = this.client;
    if (!client) return { ok: false, message: NOT_CONFIGURED };
    try {
      const { data, error } = await client.signUp({
        email,
        password,
        options: { emailRedirectTo: this.callbackUrl('/') },
      });
      if (error) return { ok: false, message: describeAuthError(error) };
      // With email confirmation on, Supabase returns a user but no session yet.
      return { ok: true, needsEmailConfirmation: !data.session };
    } catch (error) {
      return { ok: false, message: describeAuthError(error) };
    }
  }

  sendMagicLink(email: string, next = '/'): Promise<AuthResult> {
    return this.run((client) =>
      client.signInWithOtp({ email, options: { emailRedirectTo: this.callbackUrl(next) } }),
    );
  }

  /** Leaves the app for Google's sign-in page; it returns to /auth/callback. */
  signInWithGoogle(next = '/'): Promise<AuthResult> {
    return this.run((client) =>
      client.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: this.callbackUrl(next) },
      }),
    );
  }

  sendPasswordReset(email: string): Promise<AuthResult> {
    return this.run((client) =>
      client.resetPasswordForEmail(email, { redirectTo: this.callbackUrl('/reset-password') }),
    );
  }

  updatePassword(password: string): Promise<AuthResult> {
    return this.run((client) => client.updateUser({ password }));
  }

  async signOut(): Promise<void> {
    if (!this.client) return;
    // Local scope: signs this browser out even when the network is down.
    await this.client.signOut({ scope: 'local' });
    this.sessionState.set(null);
  }

  private callbackUrl(next: string): string {
    const url = new URL('/auth/callback', window.location.origin);
    url.searchParams.set('next', next);
    return url.toString();
  }

  private async run(
    action: (client: NonNullable<typeof this.client>) => Promise<{ error: AuthError | null }>,
  ): Promise<AuthResult> {
    const client = this.client;
    if (!client) return { ok: false, message: NOT_CONFIGURED };
    try {
      const { error } = await action(client);
      return error ? { ok: false, message: describeAuthError(error) } : { ok: true };
    } catch (error) {
      return { ok: false, message: describeAuthError(error) };
    }
  }
}
