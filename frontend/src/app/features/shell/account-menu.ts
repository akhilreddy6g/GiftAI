import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  output,
  signal,
  viewChild,
} from '@angular/core';

import { AuthService } from '../../core/auth/auth.service';
import { Icon } from '../../core/ui/icon';
import { ThemePicker } from './theme-picker';

/**
 * The signed-in user's email at the foot of the sidebar. Pressing it opens a panel in
 * place with the theme, "More" (which reveals Delete account) and Log out.
 */
@Component({
  selector: 'app-account-menu',
  imports: [Icon, ThemePicker],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'relative block',
    '(document:click)': 'closeIfOutside($event)',
    '(keydown.escape)': 'closeAndFocus()',
  },
  template: `
    @if (open()) {
      <div
        id="account-menu-panel"
        class="absolute inset-x-0 bottom-full mb-2 rounded-xl border border-line bg-surface p-1.5 shadow-lg"
      >
        <p class="truncate px-3 pt-2 pb-1 text-sm text-ink-muted">{{ email() }}</p>

        <div class="px-1.5 py-2">
          <p class="mb-1.5 px-1.5 text-xs font-medium text-ink-muted">Theme</p>
          <app-theme-picker />
        </div>

        <div class="my-1 border-t border-line"></div>

        <button
          type="button"
          class="menu-item"
          aria-controls="account-more"
          [attr.aria-expanded]="moreOpen()"
          (click)="moreOpen.set(!moreOpen())"
        >
          <app-icon name="more" [size]="18" />
          <span class="flex-1 text-left">More</span>
          <app-icon
            name="chevron-right"
            [size]="16"
            class="text-ink-muted transition-transform"
            [class.rotate-90]="moreOpen()"
          />
        </button>
        @if (moreOpen()) {
          <div id="account-more" class="pl-6">
            <button type="button" class="menu-item text-danger" (click)="choose(deleteAccount)">
              <app-icon name="trash" [size]="18" />
              Delete account
            </button>
          </div>
        }

        <div class="my-1 border-t border-line"></div>

        <button type="button" class="menu-item" (click)="choose(signOut)">
          <app-icon name="logout" [size]="18" />
          Log out
        </button>
      </div>
    }

    <button
      #trigger
      type="button"
      class="flex min-h-11 w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm hover:bg-surface-muted"
      aria-controls="account-menu-panel"
      [attr.aria-expanded]="open()"
      (click)="toggle()"
    >
      <span
        class="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-semibold text-accent-ink"
        aria-hidden="true"
        >{{ initial() }}</span
      >
      <span class="min-w-0 flex-1 truncate font-medium">
        <span class="sr-only">Account menu for </span>{{ email() }}
      </span>
      <app-icon name="chevron-up-down" [size]="16" class="text-ink-muted" />
    </button>
  `,
  styles: `
    .menu-item {
      display: flex;
      min-height: 2.75rem;
      width: 100%;
      align-items: center;
      gap: 0.75rem;
      border-radius: 0.5rem;
      padding: 0.5rem 0.75rem;
      font-size: 0.875rem;
    }
    .menu-item:hover {
      background: var(--surface-muted);
    }
  `,
})
export class AccountMenu {
  readonly signOut = output();
  readonly deleteAccount = output();

  private readonly auth = inject(AuthService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly trigger = viewChild.required<ElementRef<HTMLButtonElement>>('trigger');

  protected readonly open = signal(false);
  protected readonly moreOpen = signal(false);
  protected readonly email = computed(() => this.auth.email() ?? 'Your account');
  protected readonly initial = computed(() => (this.auth.email() ?? '?')[0].toUpperCase());

  protected toggle(): void {
    this.open.set(!this.open());
    this.moreOpen.set(false);
  }

  protected choose(action: { emit(): void }): void {
    this.open.set(false);
    action.emit();
  }

  protected closeIfOutside(event: MouseEvent): void {
    if (this.open() && !this.host.contains(event.target as Node)) this.open.set(false);
  }

  protected closeAndFocus(): void {
    if (!this.open()) return;
    this.open.set(false);
    this.trigger().nativeElement.focus();
  }
}
