import {
  ChangeDetectionStrategy,
  Component,
  afterNextRender,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { Router } from '@angular/router';

import { ApiError } from '../../core/api/api-error';
import { Icon } from '../../core/ui/icon';
import { ChatsStore } from './chats.store';
import { Composer } from './composer';

/** What the chat page sends as soon as it opens, carried in the navigation state. */
export interface FirstMessageState {
  firstMessage?: string;
}

const EXAMPLES = [
  'My sister turns 30 next month. She loves hiking and good coffee. Around $50.',
  'A farewell gift for a coworker who is moving to Japan, $20 to $40.',
  'Anniversary gift for my husband, he is into cooking and vinyl records, up to $150.',
];

/** The start of a new chat: its first message creates the chat. */
@Component({
  selector: 'app-home-page',
  imports: [Composer, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div class="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 py-10">
        <span
          class="mb-5 flex size-12 items-center justify-center rounded-2xl bg-accent-soft text-accent-text"
        >
          <app-icon name="gift" [size]="26" />
        </span>
        <h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">Who are you shopping for?</h1>
        <p class="mt-3 text-ink-muted">
          Tell GiftAI about them: what they're into, the occasion and your budget. It will ask a few
          questions, then suggest gifts from Amazon and explain why each one fits.
        </p>

        <h2 class="mt-8 mb-3 text-sm font-medium text-ink-muted">Try something like</h2>
        <ul class="space-y-2">
          @for (example of examples; track example) {
            <li>
              <button
                type="button"
                class="w-full rounded-xl border border-line bg-surface px-4 py-3 text-left text-sm hover:border-line-strong hover:bg-surface-muted"
                (click)="useExample(example)"
              >
                {{ example }}
              </button>
            </li>
          }
        </ul>
      </div>
    </div>

    <div class="shrink-0 border-t border-line bg-canvas px-4 pt-3 pb-4">
      <div class="mx-auto w-full max-w-2xl">
        @if (error(); as message) {
          <p class="alert-error mb-3" role="alert">{{ message }}</p>
        }
        <app-composer
          inputId="first-message"
          label="Describe who you're shopping for"
          placeholder="Who is the gift for, and what are they into?"
          [busy]="starting()"
          (send)="start($event)"
        />
      </div>
    </div>
  `,
  host: { class: 'flex min-h-0 flex-1 flex-col' },
})
export class HomePage {
  private readonly chats = inject(ChatsStore);
  private readonly router = inject(Router);
  private readonly composer = viewChild.required(Composer);

  protected readonly examples = EXAMPLES;
  protected readonly starting = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    afterNextRender(() => {
      // On wide screens the message box is the obvious next step; on phones focusing it
      // would pop the keyboard over the introduction.
      if (window.matchMedia('(min-width: 1024px)').matches) this.composer().focus();
    });
  }

  protected useExample(text: string): void {
    this.composer().restore(text);
  }

  protected async start(text: string): Promise<void> {
    this.starting.set(true);
    this.error.set(null);
    try {
      const chat = await this.chats.create();
      const state: FirstMessageState = { firstMessage: text };
      await this.router.navigate(['/chats', chat.id], { state });
    } catch (error) {
      this.error.set(ApiError.from(error).message);
      this.composer().restore(text);
    } finally {
      this.starting.set(false);
    }
  }
}
