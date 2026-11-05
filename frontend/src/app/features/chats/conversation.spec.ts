import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { API, chat, errorBody, message, turn } from '../../../testing/api-fixtures';
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
    await opening;
  });

  afterEach(() => http.verify());

  it('shows the thread oldest first', () => {
    expect(conversation.messages().map((m) => m.id)).toEqual(['m1', 'm2']);
    expect(conversation.hasOlder()).toBe(true);
  });

  it('puts older messages above the current ones', async () => {
    const loading = conversation.loadOlder();
    await settle();
    http
      .expectOne(`${API}/api/v1/chats/chat-1/messages?limit=50&cursor=older`)
      .flush({ items: [message({ id: 'm0' })], next_cursor: null });
    await loading;

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
});
