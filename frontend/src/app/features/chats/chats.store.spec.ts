import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { API, chat, errorBody } from '../../../testing/api-fixtures';
import { FakeAuth } from '../../../testing/fake-auth';
import { provideTestApp } from '../../../testing/providers';
import { ChatsStore } from './chats.store';

/** Lets the token lookup run, so the request reaches the testing backend. */
const settle = () => new Promise((resolve) => setTimeout(resolve));

describe('ChatsStore', () => {
  let store: ChatsStore;
  let http: HttpTestingController;
  let auth: FakeAuth;

  beforeEach(() => {
    auth = new FakeAuth();
    auth.signIn();
    TestBed.configureTestingModule({ providers: provideTestApp(auth) });
    store = TestBed.inject(ChatsStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the first page once', async () => {
    const loading = store.ensureLoaded();
    expect(store.isLoading()).toBe(true);
    await settle();
    http.expectOne(`${API}/api/v1/chats?limit=30`).flush({ items: [chat()], next_cursor: 'next' });
    await loading;

    expect(store.chats().map((c) => c.id)).toEqual(['chat-1']);
    expect(store.hasMore()).toBe(true);

    await store.ensureLoaded();
    http.expectNone(`${API}/api/v1/chats?limit=30`);
  });

  it('keeps the error and allows a retry when loading fails', async () => {
    const loading = store.ensureLoaded();
    await settle();
    http
      .expectOne(`${API}/api/v1/chats?limit=30`)
      .flush(errorBody('internal_error', 'Try later.'), { status: 500, statusText: 'Error' });
    await loading;

    expect(store.loadError()).toBe('Try later.');
    expect(store.isLoaded()).toBe(false);

    const retry = store.ensureLoaded();
    await settle();
    http.expectOne(`${API}/api/v1/chats?limit=30`).flush({ items: [], next_cursor: null });
    await retry;
    expect(store.isLoaded()).toBe(true);
    expect(store.loadError()).toBeNull();
  });

  it('appends older chats without duplicates', async () => {
    const loading = store.ensureLoaded();
    await settle();
    http
      .expectOne(`${API}/api/v1/chats?limit=30`)
      .flush({ items: [chat({ id: 'a' })], next_cursor: 'c1' });
    await loading;

    const more = store.loadMore();
    await settle();
    http
      .expectOne(`${API}/api/v1/chats?limit=30&cursor=c1`)
      .flush({ items: [chat({ id: 'a' }), chat({ id: 'b' })], next_cursor: null });
    await more;

    expect(store.chats().map((c) => c.id)).toEqual(['a', 'b']);
    expect(store.hasMore()).toBe(false);
  });

  it('keeps chats ordered by last activity as they change', () => {
    store.upsert(chat({ id: 'old', updated_at: '2026-11-01T00:00:00Z' }));
    store.upsert(chat({ id: 'new', updated_at: '2026-11-03T00:00:00Z' }));
    store.upsert(chat({ id: 'old', updated_at: '2026-11-04T00:00:00Z', title: 'Mom' }));

    expect(store.chats().map((c) => c.id)).toEqual(['old', 'new']);
    expect(store.find('old')?.title).toBe('Mom');
  });

  it('creates, renames and deletes chats', async () => {
    const created = store.create();
    await settle();
    const createRequest = http.expectOne(`${API}/api/v1/chats`);
    expect(createRequest.request.body).toEqual({});
    createRequest.flush(chat({ id: 'x' }));
    await created;
    expect(store.find('x')).toBeDefined();

    const renamed = store.rename('x', null);
    await settle();
    const renameRequest = http.expectOne(`${API}/api/v1/chats/x`);
    expect(renameRequest.request.body).toEqual({ title: null });
    renameRequest.flush(chat({ id: 'x', title: 'Dad, birthday' }));
    await renamed;
    expect(store.find('x')?.title).toBe('Dad, birthday');

    const removed = store.remove('x');
    await settle();
    http.expectOne(`${API}/api/v1/chats/x`).flush(null, { status: 204, statusText: 'No Content' });
    await removed;
    expect(store.find('x')).toBeUndefined();
  });

  it('forgets everything on sign-out', async () => {
    store.upsert(chat());
    await auth.signOut();

    expect(store.chats()).toEqual([]);
    expect(store.isLoaded()).toBe(false);
  });
});
