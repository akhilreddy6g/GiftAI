import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { Icon } from '../../core/ui/icon';
import { formatPlainDate } from './chat-dates';
import { Conversation, type ReplyPicks } from './conversation';
import { GiftCard } from './gift-card';

/** The gifts one reply suggested, with a button that adds them all to the Amazon cart. */
@Component({
  selector: 'app-gift-picks',
  imports: [GiftCard, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <section [attr.aria-label]="'Gift ideas (' + picks().items.length + ')'">
      <ol class="space-y-3">
        @for (pick of picks().items; track pick.id) {
          <li><app-gift-card [pick]="pick" /></li>
        }
      </ol>

      <div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        @if (picks().addAllUrl && picks().items.length > 1) {
          <a
            class="btn btn-secondary"
            [href]="picks().addAllUrl"
            target="_blank"
            rel="noopener noreferrer"
            (click)="addedAll()"
          >
            <app-icon name="cart" [size]="18" />
            Add all {{ picks().items.length }} to your Amazon cart<span class="sr-only">
              (opens in a new tab)</span
            >
          </a>
        }
        @if (orderByLabel(); as label) {
          <p class="text-sm font-medium">Order by {{ label }} so it arrives in time.</p>
        }
      </div>
      <p class="mt-2 text-xs text-ink-muted">
        Prices are from 2023 and may have changed. Amazon asks you to confirm before anything goes
        in your cart.
      </p>
    </section>
  `,
})
export class GiftPicks {
  readonly picks = input.required<ReplyPicks>();
  /** The last day to order, shown only with the newest picks. */
  readonly orderBy = input<string | null>(null);

  private readonly conversation = inject(Conversation);

  protected readonly orderByLabel = computed(() => {
    const date = this.orderBy();
    return date ? formatPlainDate(date) : null;
  });

  protected addedAll(): void {
    this.conversation.logEvent('added_to_cart', this.picks().items);
  }
}
