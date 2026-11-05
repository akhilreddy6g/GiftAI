import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { API, chat, errorBody, message, pick, product, turn } from '../../../testing/api-fixtures';
import { FakeAuth } from '../../../testing/fake-auth';
import { provideTestApp } from '../../../testing/providers';
import { ChatsStore } from './chats.store';
import { Conversation } from './conversation';

const settle = () => new Promise((resolve) => setTimeout(resolve));

describe('Conversation', () => {
  let conversation: Conversation;
  let http: HttpTestingController;

  beforeEach(async () => {
    const auth = new FakeAuth();
    auth.signIn();
    TestBed.configureTestingModule({ providers: [...provideTestApp(auth), Conversation] });
    conversation = TestBed.inject(Conversation);
    http = TestBed.inject(HttpTestingController);

    const opening = conversation.open('chat-1');
    await settle();
    http.expectOne(`${API}/api/v1/chats/chat-1/messages?limit=50`).flush({
      items: [
        message({ id: 'm2', role: 'assistant', content: 'Who is it for?' }),
        message({ id: 'm1', content: 'Hi' }),
      ],
      next_cursor: 'older',
    });
    await settle();
    http
      .expectOne(`${API}/api/v1/chats/chat-1/recommendations?message_id=m2`)
      .flush({ items: [], add_all_to_cart_urls: {}, order_by: null });
    await opening;
  });

  async function sendWithPicks() {
    const sending = conversation.send('Ideas please');
    await settle();
    http.expectOne(`${API}/api/v1/chats/chat-1/messages`).flush(
      turn({
        recommendations: [
          pick(),
          pick({ id: 'pick-2', rank: 2, product: product({ asin: 'B000MUG' }) }),
        ],
        add_all_to_cart_url: 'https://cart.test/all',
        order_by: '2026-12-07',
      }),
    );
    await sending;
  }

  afterEach(() => http.verify());

  it('shows the thread oldest first', () => {
    expect(conversation.messages().map((m) => m.id)).toEqual(['m1', 'm2']);
    expect(conversation.hasOlder()).toBe(true);
  });

  it('puts older messages above the current ones', async () => {
    const loading = conversation.loadOlder();
    await settle();
    http.expectOne(`${API}/api/v1/chats/chat-1/messages?limit=50&cursor=older`).flush({
      items: [message({ id: 'm0', role: 'assistant', content: 'Earlier ideas' })],
      next_cursor: null,
    });
    await settle();
    http.expectOne(`${API}/api/v1/chats/chat-1/recommendations?message_id=m0`).flush({
      items: [pick({ message_id: 'm0' })],
      add_all_to_cart_urls: { m0: 'https://cart.test/m0' },
      order_by: null,
    });
    await loading;
    expect(conversation.picks().get('m0')).toEqual({
      items: [pick({ message_id: 'm0' })],
      addAllUrl: 'https://cart.test/m0',
    });

    expect(conversation.messages().map((m) => m.id)).toEqual(['m0', 'm1', 'm2']);
    expect(conversation.hasOlder()).toBe(false);
  });

  it('shows the message while sending, then the saved message and the reply', async () => {
    const sending = conversation.send('  For my sister  ');
    expect(conversation.isSending()).toBe(true);
    expect(conversation.messages().at(-1)).toMatchObject({
      content: 'For my sister',
      pending: true,
    });

    await settle();
    const request = http.expectOne(`${API}/api/v1/chats/chat-1/messages`);
    expect(request.request.body).toEqual({ content: 'For my sister' });
    const reply = turn({ chat: chat({ title: 'Sister' }) });
    request.flush(reply);

    await expect(sending).resolves.toEqual({ ok: true });
    expect(conversation.messages().map((m) => m.id)).toEqual(['m1', 'm2', 'sent', 'reply']);
    expect(conversation.latestReply()?.id).toBe('reply');
    expect(conversation.isSending()).toBe(false);
    expect(TestBed.inject(ChatsStore).find('chat-1')?.title).toBe('Sister');
  });

  it('removes the unsent message and reports why when sending fails', async () => {
    const sending = conversation.send('For my sister');
    await settle();
    http
      .expectOne(`${API}/api/v1/chats/chat-1/messages`)
      .flush(errorBody('limit_reached', "You've used today's replies."), {
        status: 429,
        statusText: 'Too Many Requests',
      });

    const result = await sending;
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.message).toBe("You've used today's replies.");
    expect(conversation.messages().map((m) => m.id)).toEqual(['m1', 'm2']);
    expect(conversation.isSending()).toBe(false);
  });

  it('ignores blank messages', async () => {
    const result = await conversation.send('   ');
    expect(result.ok).toBe(false);
  });

  it('keeps the picks a reply came with, and the order-by date', async () => {
    await sendWithPicks();

    const group = conversation.picks().get('reply');
    expect(group?.items.map((item) => item.id)).toEqual(['pick-1', 'pick-2']);
    expect(group?.addAllUrl).toBe('https://cart.test/all');
    expect(conversation.orderBy()).toBe('2026-12-07');
  });

  it('still shows the chat when its picks fail to load, and can retry', async () => {
    const retrying = conversation.retryPicks();
    await settle();
    http
      .expectOne(`${API}/api/v1/chats/chat-1/recommendations?message_id=m2`)
      .flush(errorBody('internal_error', 'Something broke.'), {
        status: 500,
        statusText: 'Server Error',
      });
    await retrying;

    expect(conversation.picksError()?.message).toBe('Something broke.');
    expect(conversation.messages().length).toBe(2);
  });

  it('shows a rating at once and undoes it if saving fails', async () => {
    await sendWithPicks();
    const first = conversation.picks().get('reply')!.items[0];

    const saving = conversation.rate(first, 'up');
    expect(conversation.picks().get('reply')!.items[0].rating).toBe('up');
    await settle();
    const request = http.expectOne(`${API}/api/v1/recommendations/pick-1/rating`);
    expect(request.request.body).toEqual({ rating: 'up' });
    request.flush(errorBody('internal_error', 'Try again.'), {
      status: 500,
      statusText: 'Server Error',
    });

    expect((await saving)?.message).toBe('Try again.');
    expect(conversation.picks().get('reply')!.items[0].rating).toBeNull();
  });

  it('logs clicks and cart adds without waiting or failing', async () => {
    await sendWithPicks();
    const items = conversation.picks().get('reply')!.items;

    conversation.logEvent('added_to_cart', items);
    await settle();
    const request = http.expectOne(`${API}/api/v1/feedback/events`);
    expect(request.request.body).toEqual({
      kind: 'added_to_cart',
      recommendation_ids: ['pick-1', 'pick-2'],
    });
    request.flush(errorBody('internal_error', 'Down.'), { status: 500, statusText: 'Error' });
    await settle();
  });

  it('applies an availability vote to every card of that product', async () => {
    await sendWithPicks();
    const voting = conversation.vote('B000MUG', false);
    await settle();
    const availability = {
      status: 'likely_gone' as const,
      found_votes: 0,
      not_found_votes: 1,
      your_vote: false,
    };
    http.expectOne(`${API}/api/v1/products/B000MUG/availability`).flush(availability);

    expect(await voting).toBeNull();
    const [first, second] = conversation.picks().get('reply')!.items;
    expect(second.availability).toEqual(availability);
    expect(first.availability.status).toBe('unverified');
  });
});
