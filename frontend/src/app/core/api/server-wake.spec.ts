import { TestBed } from '@angular/core/testing';

import { SLOW_REQUEST_MS, ServerWake, isSlowByDesign } from './server-wake';

describe('ServerWake', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('reports waking only while a request is slow', () => {
    const wake = TestBed.inject(ServerWake);

    const done = wake.track();
    expect(wake.isWaking()).toBe(false);

    vi.advanceTimersByTime(SLOW_REQUEST_MS);
    expect(wake.isWaking()).toBe(true);

    done();
    expect(wake.isWaking()).toBe(false);
  });

  it('never reports a fast request', () => {
    const wake = TestBed.inject(ServerWake);

    wake.track()();
    vi.advanceTimersByTime(SLOW_REQUEST_MS * 2);

    expect(wake.isWaking()).toBe(false);
  });

  it('leaves out sending a chat message, which shows its own thinking notice', () => {
    expect(isSlowByDesign('POST', 'http://api.test/api/v1/chats/c1/messages')).toBe(true);
    expect(isSlowByDesign('GET', 'http://api.test/api/v1/chats/c1/messages')).toBe(false);
    expect(isSlowByDesign('POST', 'http://api.test/api/v1/chats')).toBe(false);
  });
});
