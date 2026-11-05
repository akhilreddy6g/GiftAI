import { TestBed } from '@angular/core/testing';

import { SLOW_REQUEST_MS, ServerWake } from './server-wake';

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
});
