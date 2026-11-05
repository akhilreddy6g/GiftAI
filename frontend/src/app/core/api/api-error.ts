import { HttpErrorResponse } from '@angular/common/http';

/** Codes the API sends in its error envelope, plus ``network_error`` for no response. */
export type ApiErrorCode =
  | 'invalid_request'
  | 'unauthorized'
  | 'not_found'
  | 'conflict'
  | 'limit_reached'
  | 'rate_limited'
  | 'service_unavailable'
  | 'internal_error'
  | 'network_error'
  | (string & {});

const NETWORK_MESSAGE =
  "We couldn't reach GiftAI. Check your connection and try again in a moment.";
const FALLBACK_MESSAGE = 'Something went wrong on our side. Please try again.';

/**
 * A failed API call, carrying the user-facing message the API wrote. Every request in the
 * app fails with this type, so components show ``message`` and never parse responses.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: ApiErrorCode,
    message: string,
    readonly requestId: string | null = null,
    /** Seconds to wait before retrying, from Retry-After on 429 and 503 responses. */
    readonly retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  static from(error: unknown): ApiError {
    if (error instanceof ApiError) return error;
    if (!(error instanceof HttpErrorResponse)) {
      return new ApiError(0, 'internal_error', FALLBACK_MESSAGE);
    }
    if (error.status === 0) {
      return new ApiError(0, 'network_error', NETWORK_MESSAGE);
    }
    const envelope = readEnvelope(error.error);
    return new ApiError(
      error.status,
      envelope?.code ?? 'internal_error',
      envelope?.message ?? FALLBACK_MESSAGE,
      envelope?.request_id ?? error.headers.get('X-Request-ID'),
      parseRetryAfter(error.headers.get('Retry-After')),
    );
  }
}

interface Envelope {
  code: string;
  message: string;
  request_id?: string;
}

function readEnvelope(body: unknown): Envelope | null {
  if (typeof body !== 'object' || body === null || !('error' in body)) return null;
  const inner: unknown = body.error;
  if (typeof inner !== 'object' || inner === null) return null;
  if (!('code' in inner) || !('message' in inner)) return null;
  const { code, message } = inner;
  if (typeof code !== 'string' || typeof message !== 'string') return null;
  const requestId = 'request_id' in inner ? inner.request_id : undefined;
  return { code, message, request_id: typeof requestId === 'string' ? requestId : undefined };
}

function parseRetryAfter(header: string | null): number | null {
  if (header === null) return null;
  const seconds = Number(header);
  return Number.isFinite(seconds) && seconds >= 0 ? Math.ceil(seconds) : null;
}
