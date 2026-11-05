import {
  ChangeDetectionStrategy,
  Component,
  type ElementRef,
  computed,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { safeRedirect } from '../../core/auth/safe-redirect';
import { Icon } from '../../core/ui/icon';
import { AuthLayout } from './auth-layout';
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from './password';

type Mode = 'sign-in' | 'sign-up' | 'magic-link' | 'forgot';

const COPY: Record<Mode, { heading: string; intro: string; submit: string }> = {
  'sign-in': {
    heading: 'Sign in',
    intro: 'Welcome back. Pick up your gift chats where you left them.',
    submit: 'Sign in',
  },
  'sign-up': {
    heading: 'Create your account',
    intro: 'Tell GiftAI about the person, and get gift ideas that fit them and your budget.',
    submit: 'Create account',
  },
  'magic-link': {
    heading: 'Sign in with an email link',
    intro: "We'll email you a link that signs you in. No password needed.",
    submit: 'Email me a link',
  },
  forgot: {
    heading: 'Reset your password',
    intro: "Enter your email and we'll send you a link to choose a new password.",
    submit: 'Send reset link',
  },
};

@Component({
  selector: 'app-sign-in-page',
  imports: [ReactiveFormsModule, AuthLayout, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './sign-in.page.html',
})
export class SignInPage {
  /** Where to go after signing in, from the query string. */
  readonly next = input<string | undefined>();
  /** Set when the user was signed out because their session ended. */
  readonly expired = input<string | undefined>();

  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly emailInput = viewChild<ElementRef<HTMLInputElement>>('emailInput');
  private readonly passwordInput = viewChild<ElementRef<HTMLInputElement>>('passwordInput');

  protected readonly mode = signal<Mode>('sign-in');
  protected readonly copy = computed(() => COPY[this.mode()]);
  protected readonly needsPassword = computed(
    () => this.mode() === 'sign-in' || this.mode() === 'sign-up',
  );
  protected readonly busy = signal(false);
  protected readonly submitted = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly minPasswordLength = MIN_PASSWORD_LENGTH;

  protected readonly form = inject(NonNullableFormBuilder).group({
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    password: ['', [Validators.required, Validators.maxLength(MAX_PASSWORD_LENGTH)]],
  });

  protected switchTo(mode: Mode): void {
    this.mode.set(mode);
    this.error.set(null);
    this.notice.set(null);
    this.submitted.set(false);
    const password = this.form.controls.password;
    password.setValidators(
      mode === 'sign-up'
        ? [
            Validators.required,
            Validators.minLength(MIN_PASSWORD_LENGTH),
            Validators.maxLength(MAX_PASSWORD_LENGTH),
          ]
        : [Validators.required, Validators.maxLength(MAX_PASSWORD_LENGTH)],
    );
    password.updateValueAndValidity();
    setTimeout(() => this.emailInput()?.nativeElement.focus());
  }

  protected showError(control: 'email' | 'password'): boolean {
    const field = this.form.controls[control];
    return field.invalid && (this.submitted() || field.touched);
  }

  protected async continueWithGoogle(): Promise<void> {
    this.error.set(null);
    this.busy.set(true);
    const result = await this.auth.signInWithGoogle(this.destination());
    // On success the browser is already leaving for Google.
    if (!result.ok) {
      this.busy.set(false);
      this.error.set(result.message);
    }
  }

  protected async submit(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    this.notice.set(null);
    const { email, password } = this.form.controls;
    if (email.invalid) {
      this.emailInput()?.nativeElement.focus();
      return;
    }
    if (this.needsPassword() && password.invalid) {
      this.passwordInput()?.nativeElement.focus();
      return;
    }

    this.busy.set(true);
    try {
      await this.run(email.value.trim(), password.value);
    } finally {
      this.busy.set(false);
    }
  }

  private async run(email: string, password: string): Promise<void> {
    switch (this.mode()) {
      case 'sign-in': {
        const result = await this.auth.signInWithPassword(email, password);
        if (result.ok) await this.router.navigateByUrl(this.destination());
        else this.error.set(result.message);
        return;
      }
      case 'sign-up': {
        const result = await this.auth.signUp(email, password);
        if (!result.ok) this.error.set(result.message);
        else if (result.needsEmailConfirmation)
          this.notice.set(`Almost there. We sent a confirmation link to ${email}.`);
        else await this.router.navigateByUrl(this.destination());
        return;
      }
      case 'magic-link': {
        const result = await this.auth.sendMagicLink(email, this.destination());
        if (result.ok) this.notice.set(`Check your inbox: we sent a sign-in link to ${email}.`);
        else this.error.set(result.message);
        return;
      }
      case 'forgot': {
        const result = await this.auth.sendPasswordReset(email);
        // Same message whether or not an account exists, so emails can't be probed.
        if (result.ok) this.notice.set(`If ${email} has an account, a reset link is on its way.`);
        else this.error.set(result.message);
        return;
      }
    }
  }

  private destination(): string {
    return safeRedirect(this.next());
  }
}
