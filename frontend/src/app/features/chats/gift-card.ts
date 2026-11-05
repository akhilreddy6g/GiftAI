import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';

import type { FeedbackKind, Rating, RecommendationRead } from '../../core/api/api-types';
import { Icon } from '../../core/ui/icon';
import { Conversation } from './conversation';

let nextId = 0;

/**
 * One suggested gift: its photo, price and rating, why it suits the person, a link to buy
 * it on Amazon, thumbs up or down, and, after the user comes back from Amazon, "Did you
 * find it?".
 */
@Component({
  selector: 'app-gift-card',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block',
    '(window:focus)': 'returned()',
    '(document:visibilitychange)': 'returned()',
  },
  templateUrl: './gift-card.html',
})
export class GiftCard {
  readonly pick = input.required<RecommendationRead>();

  private readonly conversation = inject(Conversation);

  protected readonly id = `gift-${nextId++}`;
  protected readonly product = computed(() => this.pick().product);
  protected readonly price = computed(() => formatPrice(this.product().price_2023));
  protected readonly ratingCount = computed(() =>
    this.product().rating_count.toLocaleString('en-US'),
  );
  protected readonly availability = computed(() => this.pick().availability);

  protected readonly imageFailed = signal(false);
  protected readonly ratingError = signal<string | null>(null);
  /** Set once the user opens the product, until they come back to this tab. */
  private awayAtAmazon = false;
  protected readonly askingFound = signal(false);
  protected readonly voting = signal(false);
  protected readonly voteError = signal<string | null>(null);
  protected readonly votedFound = signal<boolean | null>(null);

  protected opened(kind: FeedbackKind): void {
    this.conversation.logEvent(kind, [this.pick()]);
    if (this.availability().your_vote === null && this.votedFound() === null) {
      this.awayAtAmazon = true;
    }
  }

  protected returned(): void {
    if (!this.awayAtAmazon || document.visibilityState !== 'visible') return;
    this.awayAtAmazon = false;
    this.askingFound.set(true);
  }

  protected async rate(rating: Rating): Promise<void> {
    this.ratingError.set(null);
    const next = this.pick().rating === rating ? null : rating;
    const error = await this.conversation.rate(this.pick(), next);
    if (error) this.ratingError.set(error.message);
  }

  protected async answerFound(found: boolean): Promise<void> {
    this.voting.set(true);
    this.voteError.set(null);
    const error = await this.conversation.vote(this.product().asin, found);
    this.voting.set(false);
    if (error) {
      this.voteError.set(error.message);
      return;
    }
    this.askingFound.set(false);
    this.votedFound.set(found);
  }

  protected dismissFound(): void {
    this.askingFound.set(false);
  }
}

/** "24.99" as "$25": the dataset's 2023 prices are a guide, not a quote. */
function formatPrice(value: string): string {
  const amount = Number(value);
  return Number.isFinite(amount) ? `$${Math.round(amount).toLocaleString('en-US')}` : value;
}
