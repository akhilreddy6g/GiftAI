import { Injectable, computed, inject, signal } from '@angular/core';

import { ApiClient } from '../../core/api/api-client';
import { ApiError } from '../../core/api/api-error';
import type { MessageRead } from '../../core/api/api-types';
import { ChatsStore } from './chats.store';

/** The API's limit on one message. */
export const MAX_MESSAGE_LENGTH = 2000;
const PAGE_SIZE = 50;

/** A message in the thread; ``pending`` while the user's own message is being sent. */
export interface ThreadMessage extends MessageRead {
  pending?: boolean;
}

export type SendResult = { ok: true } | { ok: false; error: ApiError };

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

  async open(chatId: string): Promise<void> {
    this.chatId = chatId;
    this.messages.set([]);
    this.olderCursor.set(null);
    this.loadError.set(null);
    this.latestReply.set(null);
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
    } catch (error) {
      if (this.chatId === chatId) this.loadError.set(ApiError.from(error));
    } finally {
      if (this.chatId === chatId) this.isLoading.set(false);
    }
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
}
