import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { formatPlainDate } from './chat-dates';
import { type ReplyPicks } from './conversation';
import { GiftCard } from './gift-card';

/** The gifts one reply suggested, with the date to order by. */
@Component({
  selector: 'app-gift-picks',
  imports: [GiftCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <section [attr.aria-label]="'Gift ideas (' + picks().items.length + ')'">
      <ol class="space-y-3">
        @for (pick of picks().items; track pick.id) {
          <li><app-gift-card [pick]="pick" /></li>
        }
      </ol>

      @if (orderByLabel(); as label) {
        <p class="mt-3 text-sm font-medium">Order by {{ label }} so it arrives in time.</p>
      }
      <p class="mt-2 text-xs text-ink-muted">
        Prices are from 2023 and may have changed. Pick the size or color you want on Amazon.
      </p>
    </section>
  `,
})
export class GiftPicks {
  readonly picks = input.required<ReplyPicks>();
  /** The last day to order, shown only with the newest picks. */
  readonly orderBy = input<string | null>(null);

  protected readonly orderByLabel = computed(() => {
    const date = this.orderBy();
    return date ? formatPlainDate(date) : null;
  });
}
