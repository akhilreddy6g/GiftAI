import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  type ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { ServerWake } from '../../core/api/server-wake';
import { Icon } from '../../core/ui/icon';
import { Sidebar } from './sidebar';

/**
 * The signed-in layout: the chat list as a sidebar on wide screens and as a drawer on
 * phones, with the current page beside it.
 */
@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, Sidebar, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <a
      href="#main"
      class="sr-only z-50 rounded-lg bg-surface px-4 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      (click)="skipToMain($event)"
    >
      Skip to the chat
    </a>

    <div class="flex h-dvh">
      <aside
        class="hidden w-72 shrink-0 border-r border-line bg-surface lg:block"
        aria-label="Chats"
      >
        <app-sidebar />
      </aside>

      <!-- Escape closes the drawer from the keyboard; the click handler adds tapping outside it. -->
      <!-- eslint-disable-next-line @angular-eslint/template/click-events-have-key-events, @angular-eslint/template/interactive-supports-focus -->
      <dialog
        #drawer
        class="m-0 h-dvh max-h-dvh w-[min(20rem,calc(100vw-3rem))] max-w-none border-r border-line bg-surface p-0 text-ink backdrop:bg-black/50 lg:hidden"
        aria-label="Chats"
        (close)="drawerOpen.set(false)"
        (click)="closeOnBackdrop($event)"
      >
        @if (drawerOpen()) {
          <app-sidebar [inDrawer]="true" (closeRequested)="closeDrawer()" />
        }
      </dialog>

      <div class="flex min-w-0 flex-1 flex-col">
        <header class="flex h-14 shrink-0 items-center gap-1 border-b border-line px-2 lg:hidden">
          <button
            type="button"
            class="icon-btn"
            aria-label="Open chats"
            aria-haspopup="dialog"
            [attr.aria-expanded]="drawerOpen()"
            (click)="openDrawer()"
          >
            <app-icon name="menu" />
          </button>
          <span class="font-semibold">GiftAI</span>
        </header>

        @if (wake.isWaking()) {
          <p
            class="border-b border-line bg-accent-soft px-4 py-2 text-center text-sm"
            role="status"
          >
            Waking up the server. After a quiet spell the first request can take up to a minute.
          </p>
        }

        <main #main id="main" class="flex min-h-0 flex-1 flex-col" tabindex="-1">
          <router-outlet />
        </main>
      </div>
    </div>
  `,
})
export class Shell {
  protected readonly wake = inject(ServerWake);
  protected readonly drawerOpen = signal(false);
  private readonly drawer = viewChild.required<ElementRef<HTMLDialogElement>>('drawer');
  private readonly main = viewChild.required<ElementRef<HTMLElement>>('main');

  constructor() {
    // Any navigation (picking a chat, starting one) closes the drawer.
    inject(Router)
      .events.pipe(
        filter((event) => event instanceof NavigationEnd),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe(() => this.closeDrawer());
  }

  protected openDrawer(): void {
    this.drawerOpen.set(true);
    this.drawer().nativeElement.showModal();
  }

  protected closeDrawer(): void {
    const drawer = this.drawer().nativeElement;
    if (drawer.open) drawer.close();
  }

  protected closeOnBackdrop(event: MouseEvent): void {
    // A click on the dialog element itself, not its content, is a click on the backdrop.
    if (event.target === this.drawer().nativeElement) this.closeDrawer();
  }

  protected skipToMain(event: Event): void {
    event.preventDefault();
    this.main().nativeElement.focus();
  }
}
