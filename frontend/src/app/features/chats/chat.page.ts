import {
  ChangeDetectionStrategy,
  Component,
  type ElementRef,
  Injector,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { Title } from '@angular/platform-browser';
import { Router } from '@angular/router';

import { ApiClient } from '../../core/api/api-client';
import { ApiError } from '../../core/api/api-error';
import type { ChatRead } from '../../core/api/api-types';
import { ConfirmDialog } from '../../core/ui/confirm-dialog';
import { Icon } from '../../core/ui/icon';
import { formatPlainDate } from './chat-dates';
import { ChatsStore } from './chats.store';
import { Composer } from './composer';
import { Conversation } from './conversation';
import type { FirstMessageState } from './home.page';
import { MessageList } from './message-list';
import { RenameForm } from './rename-form';

/** One chat: its details, the conversation and the message box. */
@Component({
  selector: 'app-chat-page',
  imports: [Composer, ConfirmDialog, Icon, MessageList, RenameForm],
  providers: [Conversation],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'flex min-h-0 flex-1 flex-col' },
  templateUrl: './chat.page.html',
})
export class ChatPage {
  /** From the route. */
  readonly chatId = input.required<string>();

  protected readonly conversation = inject(Conversation);
  private readonly chats = inject(ChatsStore);
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly title = inject(Title);
  private readonly injector = inject(Injector);

  private readonly composer = viewChild(Composer);
  private readonly heading = viewChild<ElementRef<HTMLElement>>('heading');
  private readonly deleteDialog = viewChild.required<ConfirmDialog>('deleteDialog');

  /** Fetched when the chat isn't in the sidebar's list yet (a link opened directly). */
  private readonly fetched = signal<ChatRead | null>(null);
  protected readonly chat = computed(
    () =>
      this.chats.find(this.chatId()) ??
      (this.fetched()?.id === this.chatId() ? this.fetched() : null),
  );
  protected readonly chatError = signal<ApiError | null>(null);
  protected readonly sendError = signal<string | null>(null);
  protected readonly renaming = signal(false);
  protected readonly deleting = signal(false);
  protected readonly deleteError = signal<string | null>(null);
  protected readonly details = computed(() => describeChat(this.chat()));

  constructor() {
    effect(() => {
      const chatId = this.chatId();
      untracked(() => void this.open(chatId));
    });
    effect(() => {
      const title = this.chat()?.title;
      if (title) this.title.setTitle(`${title} · GiftAI`);
    });
  }

  protected async sendMessage(text: string): Promise<void> {
    this.sendError.set(null);
    const result = await this.conversation.send(text);
    if (!result.ok) {
      this.sendError.set(result.error.message);
      this.composer()?.restore(text);
    }
  }

  protected startRename(): void {
    this.renaming.set(true);
  }

  protected readonly saveTitle = async (title: string | null): Promise<void> => {
    this.fetched.set(await this.chats.rename(this.chatId(), title));
  };

  protected closeRename(): void {
    this.renaming.set(false);
    afterNextRender(() => this.heading()?.nativeElement.focus(), { injector: this.injector });
  }

  protected askToDelete(): void {
    this.deleteError.set(null);
    this.deleteDialog().open();
  }

  protected async deleteChat(): Promise<void> {
    this.deleting.set(true);
    this.deleteError.set(null);
    try {
      await this.chats.remove(this.chatId());
      this.deleteDialog().close();
      await this.router.navigateByUrl('/');
    } catch (error) {
      this.deleteError.set(ApiError.from(error).message);
    } finally {
      this.deleting.set(false);
    }
  }

  protected retry(): void {
    void this.open(this.chatId());
  }

  private async open(chatId: string): Promise<void> {
    this.chatError.set(null);
    this.sendError.set(null);
    this.renaming.set(false);
    const firstMessage = takeFirstMessage();

    const details = this.chats.find(chatId)
      ? Promise.resolve()
      : this.api
          .get('/api/v1/chats/{chat_id}', { path: { chat_id: chatId } })
          .then((chat) => {
            if (this.chatId() === chatId) this.fetched.set(chat);
          })
          .catch((error: unknown) => {
            if (this.chatId() === chatId) this.chatError.set(ApiError.from(error));
          });
    await Promise.all([details, this.conversation.open(chatId)]);

    if (this.chatId() !== chatId || this.chatError() || this.conversation.loadError()) return;
    if (firstMessage) await this.sendMessage(firstMessage);
    else this.composer()?.focus();
  }
}

/** Reads, once, the message the home page handed over, so a reload doesn't send it again. */
function takeFirstMessage(): string | null {
  const state = (history.state ?? {}) as FirstMessageState;
  if (!state.firstMessage) return null;
  history.replaceState({ ...history.state, firstMessage: undefined }, '');
  return state.firstMessage;
}

const OCCASIONS: Record<string, string> = {
  thank_you: 'Thank you',
  get_well: 'Get well',
  just_because: 'Just because',
  baby: 'New baby',
};

/** Short labels for what's known about the gift so far, shown under the title. */
function describeChat(chat: ChatRead | null): string[] {
  if (!chat) return [];
  const labels: string[] = [];
  if (chat.occasion) {
    labels.push(
      OCCASIONS[chat.occasion] ?? chat.occasion[0].toUpperCase() + chat.occasion.slice(1),
    );
  }
  if (chat.occasion_date) labels.push(formatPlainDate(chat.occasion_date));
  const { budget_min_usd: min, budget_max_usd: max } = chat;
  if (min !== null && max !== null) labels.push(min === max ? `$${min}` : `$${min} to $${max}`);
  else if (max !== null) labels.push(`Up to $${max}`);
  else if (min !== null) labels.push(`From $${min}`);
  return labels;
}
