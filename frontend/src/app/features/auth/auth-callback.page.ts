import {
  ChangeDetectionStrategy,
  Component,
  type OnInit,
  inject,
  input,
  signal,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { safeRedirect } from '../../core/auth/safe-redirect';
import { AuthLayout } from './auth-layout';

/**
 * Where Google sign-in, email links and password-reset links return. Supabase reads the
 * one-time code from the URL when it starts; this page then sends the user on.
 */
@Component({
  selector: 'app-auth-callback-page',
  imports: [AuthLayout, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (failure(); as message) {
      <app-auth-layout heading="That link didn't work">
        <p class="alert-error" role="alert">{{ message }}</p>
        <a routerLink="/sign-in" class="btn btn-primary mt-6 w-full">Back to sign in</a>
      </app-auth-layout>
    } @else {
      <app-auth-layout heading="Signing you in…">
        <p class="text-ink-muted" role="status">This only takes a moment.</p>
      </app-auth-layout>
    }
  `,
})
export class AuthCallbackPage implements OnInit {
  readonly next = input<string | undefined>();
  // Supabase reports a failed or expired link in the query string.
  readonly error_description = input<string | undefined>();

  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly failure = signal<string | null>(null);

  async ngOnInit(): Promise<void> {
    await this.auth.ready;
    if (this.auth.isSignedIn()) {
      await this.router.navigateByUrl(safeRedirect(this.next()), { replaceUrl: true });
      return;
    }
    this.failure.set(
      this.error_description()
        ? 'That sign-in link has expired or was already used. Request a new one from the sign-in page.'
        : "We couldn't sign you in from that link. Request a new one from the sign-in page.",
    );
  }
}
