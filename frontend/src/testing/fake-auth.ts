import { computed, signal } from '@angular/core';

import type { AuthResult, SignUpResult } from '../app/core/auth/auth.service';

/** Stands in for AuthService, so tests never reach Supabase. */
export class FakeAuth {
  readonly session = signal<{ access_token: string; user: { email: string } } | null>(null);
  readonly isConfigured = true;
  readonly isSignedIn = computed(() => this.session() !== null);
  readonly email = computed(() => this.session()?.user.email ?? null);
  readonly ready = Promise.resolve();

  token: string | null = 'test-token';
  signOutCalls = 0;
  result: AuthResult = { ok: true };
  signUpResult: SignUpResult = { ok: true };
  calls: { method: string; args: unknown[] }[] = [];
  private readonly listeners = new Set<() => void>();

  signIn(email = 'giver@example.com'): void {
    this.session.set({ access_token: 'test-token', user: { email } });
  }

  async accessToken(): Promise<string | null> {
    return this.token;
  }

  onSignOut(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async signOut(): Promise<void> {
    this.signOutCalls += 1;
    this.session.set(null);
    this.listeners.forEach((listener) => listener());
  }

  signInWithPassword(...args: unknown[]): Promise<AuthResult> {
    return this.record('signInWithPassword', args, this.result);
  }

  signUp(...args: unknown[]): Promise<SignUpResult> {
    return this.record('signUp', args, this.signUpResult);
  }

  sendMagicLink(...args: unknown[]): Promise<AuthResult> {
    return this.record('sendMagicLink', args, this.result);
  }

  signInWithGoogle(...args: unknown[]): Promise<AuthResult> {
    return this.record('signInWithGoogle', args, this.result);
  }

  sendPasswordReset(...args: unknown[]): Promise<AuthResult> {
    return this.record('sendPasswordReset', args, this.result);
  }

  updatePassword(...args: unknown[]): Promise<AuthResult> {
    return this.record('updatePassword', args, this.result);
  }

  private async record<T>(method: string, args: unknown[], result: T): Promise<T> {
    this.calls.push({ method, args });
    return result;
  }
}
