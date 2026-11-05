import {
  ChangeDetectionStrategy,
  Component,
  type ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import {
  type AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  type ValidationErrors,
  Validators,
} from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { AuthLayout } from './auth-layout';
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from './password';

function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  const password = group.get('password')?.value as string;
  const confirm = group.get('confirm')?.value as string;
  return password === confirm ? null : { mismatch: true };
}

/** Reached from a password-reset email, which signs the user in for this one step. */
@Component({
  selector: 'app-reset-password-page',
  imports: [ReactiveFormsModule, AuthLayout],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-auth-layout
      heading="Choose a new password"
      intro="You'll use it the next time you sign in."
    >
      <form [formGroup]="form" (ngSubmit)="submit()" novalidate class="space-y-5">
        <div>
          <label class="field-label" for="new-password">New password</label>
          <input
            #passwordInput
            id="new-password"
            type="password"
            class="field-input"
            formControlName="password"
            autocomplete="new-password"
            [attr.aria-invalid]="submitted() && form.controls.password.invalid"
            aria-describedby="new-password-hint"
          />
          <p id="new-password-hint" class="field-hint">At least {{ minLength }} characters.</p>
        </div>
        <div>
          <label class="field-label" for="confirm-password">Type it again</label>
          <input
            id="confirm-password"
            type="password"
            class="field-input"
            formControlName="confirm"
            autocomplete="new-password"
            [attr.aria-invalid]="submitted() && form.hasError('mismatch')"
          />
        </div>

        @if (submitted() && form.invalid) {
          <p class="alert-error" role="alert">
            @if (form.controls.password.invalid) {
              Use at least {{ minLength }} characters.
            } @else {
              The two passwords don't match.
            }
          </p>
        }
        @if (error(); as message) {
          <p class="alert-error" role="alert">{{ message }}</p>
        }

        <button type="submit" class="btn btn-primary w-full" [disabled]="busy()">
          {{ busy() ? 'Saving…' : 'Save new password' }}
        </button>
      </form>
    </app-auth-layout>
  `,
})
export class ResetPasswordPage {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly passwordInput = viewChild<ElementRef<HTMLInputElement>>('passwordInput');

  protected readonly minLength = MIN_PASSWORD_LENGTH;
  protected readonly busy = signal(false);
  protected readonly submitted = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = inject(NonNullableFormBuilder).group(
    {
      password: [
        '',
        [
          Validators.required,
          Validators.minLength(MIN_PASSWORD_LENGTH),
          Validators.maxLength(MAX_PASSWORD_LENGTH),
        ],
      ],
      confirm: [''],
    },
    { validators: passwordsMatch },
  );

  protected async submit(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid) {
      this.passwordInput()?.nativeElement.focus();
      return;
    }
    this.busy.set(true);
    const result = await this.auth.updatePassword(this.form.controls.password.value);
    this.busy.set(false);
    if (result.ok) await this.router.navigateByUrl('/');
    else this.error.set(result.message);
  }
}
