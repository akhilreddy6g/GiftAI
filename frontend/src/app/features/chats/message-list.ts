import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  effect,
  inject,
  input,
  output,
  untracked,
} from '@angular/core';

import type { ThreadMessage } from './conversation';

/**
 * The conversation, oldest message first. It follows new messages to the bottom, and
 * keeps the reader's place when older messages are loaded above.
 */
@Component({
  selector: 'app-message-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block overflow-y-auto' },
  template: `
    <div class="mx-auto w-full max-w-3xl px-4 py-6">
      @if (hasOlder()) {
        <div class="mb-6 text-center">
          <button
            type="button"
            class="btn btn-secondary"
            [disabled]="loadingOlder()"
            (click)="loadOlder.emit()"
          >
            {{ loadingOlder() ? 'Loading…' : 'Show earlier messages' }}
          </button>
        </div>
      }

      @if (loading()) {
        <p class="text-center text-sm text-ink-muted" role="status">Loading the conversation…</p>
      } @else if (loadError(); as message) {
        <div class="text-center">
          <p class="text-sm text-ink-muted" role="alert">{{ message }}</p>
          <button type="button" class="btn btn-secondary mt-3" (click)="retry.emit()">
            Try again
          </button>
        </div>
      } @else {
        <ol class="space-y-4" aria-label="Conversation">
          @if (messages().length === 0 && !thinking()) {
            <li class="flex">
              <div
                class="max-w-[85%] rounded-2xl rounded-bl-md border border-line bg-surface px-4 py-3"
              >
                <span class="sr-only">GiftAI said: </span>
                Hi! Who are you shopping for? Tell me what they're into, the occasion and your
                budget, and I'll suggest a few gifts.
              </div>
            </li>
          }
          @for (message of messages(); track message.id) {
            <li class="flex" [class.justify-end]="message.role === 'user'">
              <div
                class="max-w-[85%] rounded-2xl px-4 py-3 break-words whitespace-pre-wrap"
                [class]="
                  message.role === 'user'
                    ? 'rounded-br-md bg-accent-soft text-ink'
                    : 'rounded-bl-md border border-line bg-surface'
                "
                [class.opacity-70]="message.pending"
              >
                <span class="sr-only">{{
                  message.role === 'user' ? 'You said: ' : 'GiftAI said: '
                }}</span
                >{{ message.content }}
                @if (message.pending) {
                  <span class="sr-only"> (sending)</span>
                }
              </div>
            </li>
          }
          @if (thinking()) {
            <li class="flex">
              <div
                class="flex items-center gap-2 rounded-2xl rounded-bl-md border border-line bg-surface px-4 py-3 text-sm text-ink-muted"
                role="status"
              >
                <span class="flex gap-1" aria-hidden="true">
                  <span class="size-1.5 animate-bounce rounded-full bg-ink-muted"></span>
                  <span
                    class="size-1.5 animate-bounce rounded-full bg-ink-muted [animation-delay:150ms]"
                  ></span>
                  <span
                    class="size-1.5 animate-bounce rounded-full bg-ink-muted [animation-delay:300ms]"
                  ></span>
                </span>
                GiftAI is thinking…
              </div>
            </li>
          }
        </ol>
      }
    </div>
  `,
})
export class MessageList {
  readonly messages = input.required<ThreadMessage[]>();
  readonly loading = input(false);
  readonly loadError = input<string | null>(null);
  readonly hasOlder = input(false);
  readonly loadingOlder = input(false);
  /** True while the assistant is working on a reply. */
  readonly thinking = input(false);

  readonly loadOlder = output();
  readonly retry = output();

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly injector = inject(Injector);
  private lastId: string | undefined;

  constructor() {
    effect(() => {
      const messages = this.messages();
      this.thinking();
      this.loading();
      untracked(() => this.keepPosition(messages));
    });
  }

  private keepPosition(messages: ThreadMessage[]): void {
    const newestId = messages.at(-1)?.id;
    // Same newest message: older ones were added above, so hold the reader's place.
    const prepended = newestId !== undefined && newestId === this.lastId;
    this.lastId = newestId;
    const distanceFromBottom = this.host.scrollHeight - this.host.scrollTop;
    afterNextRender(
      () => {
        this.host.scrollTop = prepended
          ? this.host.scrollHeight - distanceFromBottom
          : this.host.scrollHeight;
      },
      { injector: this.injector },
    );
  }
}
