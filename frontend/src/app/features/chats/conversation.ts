import { Injectable, computed, inject, signal } from '@angular/core';

import { ApiClient } from '../../core/api/api-client';
import { ApiError } from '../../core/api/api-error';
import type {
  FeedbackKind,
  MessageRead,
  ProductAvailability,
  Rating,
  RecommendationList,
  RecommendationRead,
} from '../../core/api/api-types';
import { ChatsStore } from './chats.store';

/** The API's limit on one message. */
export const MAX_MESSAGE_LENGTH = 2000;
const PAGE_SIZE = 50;

/** A message in the thread; ``pending`` while the user's own message is being sent. */
export interface ThreadMessage extends MessageRead {
  pending?: boolean;
}

export type SendResult = { ok: true } | { ok: false; error: ApiError };

/** The gifts one assistant reply suggested, in the order it gave them. */
export interface ReplyPicks {
  items: RecommendationRead[];
  /** Adds all of them to the user's Amazon cart at once. */
  addAllUrl: string | null;
}

/**
 * One chat's messages, oldest first, and sending a new one. The API saves a message only
 * together with the assistant's reply, so a failed send leaves nothing behind and the
 * user's text goes back into the composer.
 */
@Injectable()
export class Conversation {
  private readonly api = inject(ApiClient);
  private readonly chats = inject(ChatsStore);

  private chatId: string | null = null;
  private readonly olderCursor = signal<string | null>(null);

  readonly messages = signal<ThreadMessage[]>([]);
  readonly isLoading = signal(false);
  readonly loadError = signal<ApiError | null>(null);
  readonly isLoadingOlder = signal(false);
  readonly hasOlder = computed(() => this.olderCursor() !== null);
  readonly isSending = signal(false);
  /** The newest reply from the assistant, for the screen-reader announcement. */
  readonly latestReply = signal<MessageRead | null>(null);
  /** Gift picks by the id of the reply that suggested them. */
  readonly picks = signal<ReadonlyMap<string, ReplyPicks>>(new Map());
  /** The last day to order so a gift arrives in time, when the chat has a date. */
  readonly orderBy = signal<string | null>(null);
  /** Set when the messages loaded but their gift picks didn't. */
  readonly picksError = signal<ApiError | null>(null);

  async open(chatId: string): Promise<void> {
    this.chatId = chatId;
    this.messages.set([]);
    this.olderCursor.set(null);
    this.loadError.set(null);
    this.latestReply.set(null);
    this.picks.set(new Map());
    this.orderBy.set(null);
    this.picksError.set(null);
    this.isSending.set(false);
    this.isLoading.set(true);
    try {
      const page = await this.api.get('/api/v1/chats/{chat_id}/messages', {
        path: { chat_id: chatId },
        query: { limit: PAGE_SIZE },
      });
      if (this.chatId !== chatId) return;
      // The API pages newest first; the thread reads oldest first.
      this.messages.set([...page.items].reverse());
      this.olderCursor.set(page.next_cursor);
      await this.loadPicks(chatId, page.items);
    } catch (error) {
      if (this.chatId === chatId) this.loadError.set(ApiError.from(error));
    } finally {
      if (this.chatId === chatId) this.isLoading.set(false);
    }
  }

  /** Tries again to load the picks of every reply in the thread. */
  async retryPicks(): Promise<void> {
    if (this.chatId) await this.loadPicks(this.chatId, this.messages());
  }

  async loadOlder(): Promise<void> {
    const chatId = this.chatId;
    const cursor = this.olderCursor();
    if (!chatId || !cursor || this.isLoadingOlder()) return;
    this.isLoadingOlder.set(true);
    try {
      const page = await this.api.get('/api/v1/chats/{chat_id}/messages', {
        path: { chat_id: chatId },
        query: { limit: PAGE_SIZE, cursor },
      });
      if (this.chatId !== chatId) return;
      this.messages.update((messages) => [...[...page.items].reverse(), ...messages]);
      this.olderCursor.set(page.next_cursor);
      await this.loadPicks(chatId, page.items);
    } catch (error) {
      if (this.chatId === chatId) this.loadError.set(ApiError.from(error));
    } finally {
      this.isLoadingOlder.set(false);
    }
  }

  async send(text: string): Promise<SendResult> {
    const chatId = this.chatId;
    const content = text.trim();
    if (!chatId || !content || this.isSending()) {
      return { ok: false, error: new ApiError(0, 'invalid_request', 'Write a message first.') };
    }
    const placeholder: ThreadMessage = {
      id: `pending-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      pending: true,
    };
    this.messages.update((messages) => [...messages, placeholder]);
    this.isSending.set(true);
    try {
      const turn = await this.api.post('/api/v1/chats/{chat_id}/messages', {
        path: { chat_id: chatId },
        body: { content },
      });
      this.chats.upsert(turn.chat);
      if (this.chatId === chatId) {
        this.messages.update((messages) => [
          ...messages.filter((message) => message !== placeholder),
          turn.message,
          turn.reply,
        ]);
        if (turn.recommendations.length) {
          this.picks.update((picks) =>
            new Map(picks).set(turn.reply.id, {
              items: turn.recommendations,
              addAllUrl: turn.add_all_to_cart_url,
            }),
          );
        }
        this.orderBy.set(turn.order_by);
        this.latestReply.set(turn.reply);
      }
      return { ok: true };
    } catch (error) {
      if (this.chatId === chatId) {
        this.messages.update((messages) => messages.filter((message) => message !== placeholder));
      }
      return { ok: false, error: ApiError.from(error) };
    } finally {
      if (this.chatId === chatId) this.isSending.set(false);
    }
  }

  /** Logs that the user opened or added to their cart these picks. Best effort: a lost
   * log line is not worth an error on screen. */
  logEvent(kind: FeedbackKind, picks: readonly RecommendationRead[]): void {
    if (!picks.length) return;
    this.api
      .post('/api/v1/feedback/events', {
        body: { kind, recommendation_ids: picks.map((pick) => pick.id) },
      })
      .catch(() => undefined);
  }

  /** Thumbs up or down, or ``null`` to clear. Shown at once; undone if saving fails. */
  async rate(pick: RecommendationRead, rating: Rating | null): Promise<ApiError | null> {
    const before = pick.rating;
    this.updatePicks((item) => (item.id === pick.id ? { ...item, rating } : item));
    try {
      await this.api.put('/api/v1/recommendations/{recommendation_id}/rating', {
        path: { recommendation_id: pick.id },
        body: { rating },
      });
      return null;
    } catch (error) {
      this.updatePicks((item) => (item.id === pick.id ? { ...item, rating: before } : item));
      return ApiError.from(error);
    }
  }

  /** The user's answer to "Did you find it on Amazon?", applied to every card of it. */
  async vote(asin: string, found: boolean): Promise<ApiError | null> {
    try {
      const availability = await this.api.put('/api/v1/products/{asin}/availability', {
        path: { asin },
        body: { found },
      });
      this.setAvailability(asin, availability);
      return null;
    } catch (error) {
      return ApiError.from(error);
    }
  }

  private setAvailability(asin: string, availability: ProductAvailability): void {
    this.updatePicks((item) => (item.product.asin === asin ? { ...item, availability } : item));
  }

  private updatePicks(change: (item: RecommendationRead) => RecommendationRead): void {
    this.picks.update((picks) => {
      const next = new Map<string, ReplyPicks>();
      for (const [id, group] of picks) next.set(id, { ...group, items: group.items.map(change) });
      return next;
    });
  }

  private async loadPicks(chatId: string, messages: readonly MessageRead[]): Promise<void> {
    const replyIds = messages.filter((m) => m.role === 'assistant').map((m) => m.id);
    if (!replyIds.length) return;
    this.picksError.set(null);
    try {
      const list = await this.api.get('/api/v1/chats/{chat_id}/recommendations', {
        path: { chat_id: chatId },
        query: { message_id: replyIds },
      });
      if (this.chatId !== chatId) return;
      this.picks.update((picks) => withPicks(picks, list));
      this.orderBy.set(list.order_by);
    } catch (error) {
      // The conversation is still useful without its cards, so this isn't fatal.
      if (this.chatId === chatId) this.picksError.set(ApiError.from(error));
    }
  }
}

function withPicks(
  current: ReadonlyMap<string, ReplyPicks>,
  list: RecommendationList,
): ReadonlyMap<string, ReplyPicks> {
  const next = new Map(current);
  for (const item of list.items) {
    const group = next.get(item.message_id);
    if (group && group.items.some((existing) => existing.id === item.id)) continue;
    next.set(item.message_id, {
      items: [...(group?.items ?? []), item],
      addAllUrl: list.add_all_to_cart_urls[item.message_id] ?? null,
    });
  }
  return next;
}
