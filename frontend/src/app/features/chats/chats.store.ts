import { Injectable, computed, inject, signal } from '@angular/core';

import { ApiClient } from '../../core/api/api-client';
import { ApiError } from '../../core/api/api-error';
import type { ChatRead } from '../../core/api/api-types';
import { AuthService } from '../../core/auth/auth.service';

const PAGE_SIZE = 30;

/**
 * The signed-in user's chats, most recently active first, shared by the sidebar and the
 * chat pages. Cleared on sign-out so the next account never sees them.
 */
@Injectable({ providedIn: 'root' })
export class ChatsStore {
  private readonly api = inject(ApiClient);

  private readonly items = signal<ChatRead[]>([]);
  private readonly nextCursor = signal<string | null>(null);
  private readonly state = signal<'idle' | 'loading' | 'loaded' | 'failed'>('idle');
  private readonly loadingMoreState = signal(false);
  /** Bumped on reset, so responses for a previous account are dropped. */
  private generation = 0;

  readonly chats = this.items.asReadonly();
  readonly isLoading = computed(() => this.state() === 'loading');
  readonly isLoaded = computed(() => this.state() === 'loaded');
  readonly loadError = signal<string | null>(null);
  readonly hasMore = computed(() => this.nextCursor() !== null);
  readonly isLoadingMore = this.loadingMoreState.asReadonly();

  constructor() {
    inject(AuthService).onSignOut(() => this.reset());
  }

  /** Loads the first page, once; later calls do nothing unless the last load failed. */
  async ensureLoaded(): Promise<void> {
    if (this.state() === 'loading' || this.state() === 'loaded') return;
    const generation = this.generation;
    this.state.set('loading');
    this.loadError.set(null);
    try {
      const page = await this.api.get('/api/v1/chats', { query: { limit: PAGE_SIZE } });
      if (generation !== this.generation) return;
      this.items.set(page.items);
      this.nextCursor.set(page.next_cursor);
      this.state.set('loaded');
    } catch (error) {
      if (generation !== this.generation) return;
      this.loadError.set(ApiError.from(error).message);
      this.state.set('failed');
    }
  }

  async loadMore(): Promise<void> {
    const cursor = this.nextCursor();
    if (!cursor || this.loadingMoreState()) return;
    const generation = this.generation;
    this.loadingMoreState.set(true);
    try {
      const page = await this.api.get('/api/v1/chats', { query: { limit: PAGE_SIZE, cursor } });
      if (generation !== this.generation) return;
      const known = new Set(this.items().map((chat) => chat.id));
      this.items.update((chats) => [...chats, ...page.items.filter((c) => !known.has(c.id))]);
      this.nextCursor.set(page.next_cursor);
    } catch (error) {
      if (generation === this.generation) this.loadError.set(ApiError.from(error).message);
    } finally {
      this.loadingMoreState.set(false);
    }
  }

  /** Starts an empty chat; the assistant fills in the details as the user talks. */
  async create(): Promise<ChatRead> {
    const chat = await this.api.post('/api/v1/chats', { body: {} });
    this.upsert(chat);
    return chat;
  }

  /** A new title, or null to go back to the automatic one. */
  async rename(chatId: string, title: string | null): Promise<ChatRead> {
    const chat = await this.api.patch('/api/v1/chats/{chat_id}', {
      path: { chat_id: chatId },
      body: { title },
    });
    this.upsert(chat);
    return chat;
  }

  async remove(chatId: string): Promise<void> {
    await this.api.delete('/api/v1/chats/{chat_id}', { path: { chat_id: chatId } });
    this.items.update((chats) => chats.filter((chat) => chat.id !== chatId));
  }

  find(chatId: string): ChatRead | undefined {
    return this.items().find((chat) => chat.id === chatId);
  }

  /** Adds or replaces a chat, keeping the list ordered by last activity. */
  upsert(chat: ChatRead): void {
    this.items.update((chats) =>
      [chat, ...chats.filter((existing) => existing.id !== chat.id)].sort(
        (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at),
      ),
    );
  }

  private reset(): void {
    this.generation += 1;
    this.items.set([]);
    this.nextCursor.set(null);
    this.state.set('idle');
    this.loadError.set(null);
    this.loadingMoreState.set(false);
  }
}
