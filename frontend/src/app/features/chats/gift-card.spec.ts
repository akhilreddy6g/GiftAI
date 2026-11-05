import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import type { RecommendationRead } from '../../core/api/api-types';
import { API, pick } from '../../../testing/api-fixtures';
import { FakeAuth } from '../../../testing/fake-auth';
import { provideTestApp } from '../../../testing/providers';
import { Conversation } from './conversation';
import { GiftCard } from './gift-card';

const settle = () => new Promise((resolve) => setTimeout(resolve));

describe('GiftCard', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    const auth = new FakeAuth();
    auth.signIn();
    TestBed.configureTestingModule({ providers: [...provideTestApp(auth), Conversation] });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function render(item: RecommendationRead = pick()) {
    const fixture = TestBed.createComponent(GiftCard);
    fixture.componentRef.setInput('pick', item);
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    const link = (text: string) =>
      [...element.querySelectorAll('a')].find((a) => a.textContent?.includes(text))!;
    const button = (text: string) =>
      [...element.querySelectorAll('button')].find(
        (b) => b.textContent?.includes(text) || b.getAttribute('aria-label') === text,
      )!;
    return { fixture, element, link, button };
  }

  async function expectEvent(kind: string) {
    await settle();
    const request = http.expectOne(`${API}/api/v1/feedback/events`);
    expect(request.request.body).toEqual({ kind, recommendation_ids: ['pick-1'] });
    request.flush(null, { status: 204, statusText: 'No Content' });
  }

  async function comeBack(fixture: { detectChanges(): void }) {
    window.dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    await settle();
  }

  it('shows the photo, price, rating and reason', () => {
    const { element } = render();

    const image = element.querySelector('img')!;
    expect(image.getAttribute('src')).toBe('https://images.test/B000COFFEE.jpg');
    expect(image.getAttribute('loading')).toBe('lazy');
    expect(element.querySelector('h3')?.textContent).toContain('Pour-over coffee kit');
    expect(element.textContent).toContain('$35');
    expect(element.textContent).toContain('4.6');
    expect(element.textContent).toContain('1,234');
    expect(element.textContent).toContain('She loves slow mornings');
    expect(element.querySelector('details')).toBeNull();
  });

  it('sends Buy on Amazon to the product page, where the size or color is chosen', () => {
    const { link } = render();

    const buy = link('Buy on Amazon');
    expect(buy.href).toBe('https://www.amazon.com/dp/B000COFFEE');
    expect(buy.target).toBe('_blank');
    expect(buy.rel).toContain('noopener');
  });

  it('logs buying intent, then asks whether they found it once they come back', async () => {
    const { fixture, element, link, button } = render();
    const cart = link('Buy on Amazon');
    cart.addEventListener('click', (event) => event.preventDefault());

    cart.click();
    await expectEvent('added_to_cart');
    expect(element.textContent).not.toContain('Did you find it on Amazon?');

    await comeBack(fixture);
    expect(element.textContent).toContain('Did you find it on Amazon?');

    button("No, I couldn't find it").click();
    await settle();
    const vote = http.expectOne(`${API}/api/v1/products/B000COFFEE/availability`);
    expect(vote.request.method).toBe('PUT');
    expect(vote.request.body).toEqual({ found: false });
    vote.flush({ status: 'likely_gone', found_votes: 0, not_found_votes: 1, your_vote: false });
    await settle();
    fixture.detectChanges();

    expect(element.textContent).not.toContain('Did you find it on Amazon?');
    expect(link('Search Amazon for something like it').href).toBe(
      'https://www.amazon.com/s?k=Pour-over+coffee+kit',
    );
  });

  it("doesn't ask someone who already answered for this product", async () => {
    const { fixture, element } = render(
      pick({
        availability: { status: 'verified', found_votes: 3, not_found_votes: 0, your_vote: true },
      }),
    );
    expect(element.textContent).toContain('Found on Amazon by 3 people');
    const view = element.querySelector<HTMLAnchorElement>('h3 a')!;
    view.addEventListener('click', (event) => event.preventDefault());

    view.click();
    await expectEvent('clicked');
    await comeBack(fixture);

    expect(element.textContent).not.toContain('Did you find it on Amazon?');
  });

  it('warns when others could not find it and offers a search instead', () => {
    const { element, link } = render(
      pick({
        availability: {
          status: 'likely_gone',
          found_votes: 0,
          not_found_votes: 2,
          your_vote: null,
        },
      }),
    );

    expect(element.textContent).toContain("Others couldn't find this on Amazon lately.");
    expect(link('Search for it').href).toBe('https://www.amazon.com/s?k=Pour-over+coffee+kit');
  });

  it('saves thumbs up, and a second press clears it', async () => {
    const { fixture, button } = render();

    button('Good idea').click();
    await settle();
    http
      .expectOne(`${API}/api/v1/recommendations/pick-1/rating`)
      .flush(null, { status: 204, statusText: 'No Content' });

    fixture.componentRef.setInput('pick', pick({ rating: 'up' }));
    fixture.detectChanges();
    expect(button('Good idea').getAttribute('aria-pressed')).toBe('true');
    expect(button('Not for them').getAttribute('aria-pressed')).toBe('false');

    button('Good idea').click();
    await settle();
    const clearing = http.expectOne(`${API}/api/v1/recommendations/pick-1/rating`);
    expect(clearing.request.body).toEqual({ rating: null });
    clearing.flush(null, { status: 204, statusText: 'No Content' });
  });

  it('shows a gift icon when the photo fails to load', () => {
    const { fixture, element } = render();

    element.querySelector('img')!.dispatchEvent(new Event('error'));
    fixture.detectChanges();

    expect(element.querySelector('img')).toBeNull();
    expect(element.querySelector('app-icon')).not.toBeNull();
  });
});
