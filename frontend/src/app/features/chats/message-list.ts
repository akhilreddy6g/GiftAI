import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  output,
  untracked,
} from '@angular/core';

import type { ReplyPicks, ThreadMessage } from './conversation';
import { GiftPicks } from './gift-picks';
import { replyTextAboveCards } from './reply-text';

/**
 * The conversation, oldest message first. It follows new messages to the bottom, and
 * keeps the reader's place when older messages are loaded above.
 */
@Component({
  selector: 'app-message-list',
  imports: [GiftPicks],
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
            @let replyPicks = picks().get(message.id);
            <li
              class="flex flex-col"
              [class.items-end]="message.role === 'user'"
              [attr.data-message-id]="message.id"
            >
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
                >{{ replyPicks ? replyTextAboveCards(message.content) : message.content }}
                @if (message.pending) {
                  <span class="sr-only"> (sending)</span>
                }
              </div>
              @if (replyPicks) {
                <app-gift-picks
                  class="mt-3 w-full"
                  [picks]="replyPicks"
                  [orderBy]="message.id === newestPicksId() ? orderBy() : null"
                />
              }
            </li>
          }
          @if (picksError(); as error) {
            <li class="alert-error">
              <p role="alert">The gift ideas in this chat didn't load. {{ error }}</p>
              <button type="button" class="link mt-1" (click)="retryPicks.emit()">Try again</button>
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
  /** Gift picks by the id of the reply that suggested them. */
  readonly picks = input<ReadonlyMap<string, ReplyPicks>>(new Map());
  readonly orderBy = input<string | null>(null);
  readonly picksError = input<string | null>(null);

  readonly loadOlder = output();
  readonly retry = output();
  readonly retryPicks = output();

  protected readonly replyTextAboveCards = replyTextAboveCards;
  /** The newest reply with picks: the order-by date goes with it. */
  protected readonly newestPicksId = computed(() => {
    const picks = this.picks();
    return (
      this.messages()
        .filter((message) => picks.has(message.id))
        .at(-1)?.id ?? null
    );
  });

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly injector = inject(Injector);
  private lastId: string | undefined;

  constructor() {
    effect(() => {
      const messages = this.messages();
      this.thinking();
      this.picks();
      this.loading();
      untracked(() => this.keepPosition(messages));
    });
  }

  private keepPosition(messages: ThreadMessage[]): void {
    const newest = messages.at(-1);
    // Same newest message: older ones (or gift cards) were added above, so hold the place.
    const prepended = newest !== undefined && newest.id === this.lastId;
    this.lastId = newest?.id;
    const distanceFromBottom = this.host.scrollHeight - this.host.scrollTop;
    // A reply with gift cards is taller than the screen: show it from its start.
    const showFromTop = !prepended && newest !== undefined && this.picks().has(newest.id);
    afterNextRender(
      () => {
        const reply = showFromTop
          ? this.host.querySelector(`[data-message-id="${newest.id}"]`)
          : null;
        if (reply) {
          this.host.scrollTop +=
            reply.getBoundingClientRect().top - this.host.getBoundingClientRect().top - 16;
        } else {
          this.host.scrollTop = prepended
            ? this.host.scrollHeight - distanceFromBottom
            : this.host.scrollHeight;
        }
      },
      { injector: this.injector },
    );
  }
}
