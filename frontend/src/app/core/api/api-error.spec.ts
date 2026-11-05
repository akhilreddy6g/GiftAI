import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';

import { ApiError } from './api-error';

describe('ApiError.from', () => {
  it('reads the API error envelope and the retry delay', () => {
    const error = ApiError.from(
      new HttpErrorResponse({
        status: 429,
        error: { error: { code: 'rate_limited', message: 'Slow down.', request_id: 'r-1' } },
        headers: new HttpHeaders({ 'Retry-After': '42' }),
      }),
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(429);
    expect(error.code).toBe('rate_limited');
    expect(error.message).toBe('Slow down.');
    expect(error.requestId).toBe('r-1');
    expect(error.retryAfterSeconds).toBe(42);
  });

  it('explains a failed connection instead of showing status 0', () => {
    const error = ApiError.from(new HttpErrorResponse({ status: 0 }));

    expect(error.code).toBe('network_error');
    expect(error.message).toContain("couldn't reach GiftAI");
  });

  it('falls back to a friendly message when the body is not the envelope', () => {
    const error = ApiError.from(
      new HttpErrorResponse({
        status: 502,
        error: '<html>Bad gateway</html>',
        headers: new HttpHeaders({ 'X-Request-ID': 'from-header' }),
      }),
    );

    expect(error.code).toBe('internal_error');
    expect(error.message).toBe('Something went wrong on our side. Please try again.');
    expect(error.requestId).toBe('from-header');
    expect(error.retryAfterSeconds).toBeNull();
  });

  it('returns the same error when given an ApiError', () => {
    const original = new ApiError(404, 'not_found', 'Gone.');
    expect(ApiError.from(original)).toBe(original);
  });

  it('wraps anything else as an internal error', () => {
    expect(ApiError.from(new TypeError('boom')).code).toBe('internal_error');
  });
});
