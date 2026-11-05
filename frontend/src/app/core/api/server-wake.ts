import { type HttpInterceptorFn } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';

import { ApiClient } from './api-client';

/** How long an API call may take before the app says the server is waking up. */
export const SLOW_REQUEST_MS = 5000;

/**
 * Notices API calls that take unusually long. The free API host sleeps when idle and the
 * first call afterwards can take up to a minute, so the app says so instead of looking stuck.
 */
@Injectable({ providedIn: 'root' })
export class ServerWake {
  private readonly slowRequests = signal(0);

  readonly isWaking = computed(() => this.slowRequests() > 0);

  track(): () => void {
    let slow = false;
    const timer = setTimeout(() => {
      slow = true;
      this.slowRequests.update((count) => count + 1);
    }, SLOW_REQUEST_MS);
    return () => {
      clearTimeout(timer);
      if (slow) this.slowRequests.update((count) => count - 1);
    };
  }
}

export const serverWakeInterceptor: HttpInterceptorFn = (request, next) => {
  if (!inject(ApiClient).isApiUrl(request.url)) return next(request);
  const done = inject(ServerWake).track();
  return next(request).pipe(finalize(done));
};
