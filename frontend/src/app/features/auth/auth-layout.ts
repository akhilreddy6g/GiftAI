import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { Icon } from '../../core/ui/icon';

/** The centered card every sign-in page sits in. */
@Component({
  selector: 'app-auth-layout',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="flex min-h-dvh items-start justify-center px-4 py-10 sm:items-center sm:py-16">
      <div class="w-full max-w-md">
        <p class="mb-8 flex items-center justify-center gap-2 text-lg font-semibold">
          <span
            class="flex size-9 items-center justify-center rounded-lg bg-accent text-accent-ink"
          >
            <app-icon name="gift" />
          </span>
          GiftAI
        </p>
        <div class="rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8">
          <h1 class="text-2xl font-semibold tracking-tight">{{ heading() }}</h1>
          @if (intro()) {
            <p class="mt-2 mb-6 text-ink-muted">{{ intro() }}</p>
          } @else {
            <div class="mb-6"></div>
          }
          <ng-content />
        </div>
      </div>
    </main>
  `,
})
export class AuthLayout {
  readonly heading = input.required<string>();
  readonly intro = input<string>('');
}
