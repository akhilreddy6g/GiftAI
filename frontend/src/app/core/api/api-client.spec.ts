import { HttpClient } from '@angular/common/http';
import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { API, chat, errorBody } from '../../../testing/api-fixtures';
import { FakeAuth } from '../../../testing/fake-auth';
import { provideTestApp } from '../../../testing/providers';
import { ApiClient } from './api-client';
import { ApiError } from './api-error';

describe('ApiClient', () => {
  let api: ApiClient;
  let http: HttpTestingController;
  let auth: FakeAuth;

  beforeEach(() => {
    auth = new FakeAuth();
    auth.signIn();
    TestBed.configureTestingModule({ providers: provideTestApp(auth) });
    api = TestBed.inject(ApiClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('fills path parameters, drops empty query values and sends the token', async () => {
    const response = api.get('/api/v1/chats/{chat_id}/messages', {
      path: { chat_id: 'a b' },
      query: { limit: 20, cursor: null },
    });
    await Promise.resolve();

    const request = http.expectOne(`${API}/api/v1/chats/a%20b/messages?limit=20`);
    expect(request.request.method).toBe('GET');
    expect(request.request.headers.get('Authorization')).toBe('Bearer test-token');
    request.flush({ items: [], next_cursor: null });

    await expect(response).resolves.toEqual({ items: [], next_cursor: null });
  });

  it('sends JSON bodies', async () => {
    const response = api.patch('/api/v1/chats/{chat_id}', {
      path: { chat_id: 'chat-1' },
      body: { title: 'Mom' },
    });
    await Promise.resolve();

    const request = http.expectOne(`${API}/api/v1/chats/chat-1`);
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ title: 'Mom' });
    request.flush(chat({ title: 'Mom' }));

    await expect(response).resolves.toMatchObject({ title: 'Mom' });
  });

  it('rejects with the API error message', async () => {
    const response = api.get('/api/v1/chats', {});
    await Promise.resolve();

    http
      .expectOne(`${API}/api/v1/chats`)
      .flush(errorBody('service_unavailable', 'GiftAI is busy.'), {
        status: 503,
        statusText: 'Service Unavailable',
      });

    const error = await response.catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe('GiftAI is busy.');
  });

  it('signs the user out and asks them to sign in again on 401', async () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const response = api.get('/api/v1/me', {}).catch((e: unknown) => e);
    await Promise.resolve();

    http.expectOne(`${API}/api/v1/me`).flush(errorBody('unauthorized', 'Please sign in.'), {
      status: 401,
      statusText: 'Unauthorized',
    });

    expect(await response).toBeInstanceOf(ApiError);
    await vi.waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(auth.signOutCalls).toBe(1);
    expect(navigate.mock.calls[0][0]).toEqual(['/sign-in']);
  });

  it('leaves requests to other hosts alone', async () => {
    const response = firstValueFrom(TestBed.inject(HttpClient).get('https://elsewhere.test/x'));

    const request = http.expectOne('https://elsewhere.test/x');
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({});
    await response;
  });

  it('recognises only its own API URLs', () => {
    expect(api.isApiUrl(`${API}/api/v1/chats`)).toBe(true);
    expect(api.isApiUrl(`${API}.evil.test/api`)).toBe(false);
  });
});
