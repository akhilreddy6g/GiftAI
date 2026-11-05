import { HttpErrorResponse, type HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, switchMap, throwError } from 'rxjs';

import { AuthService } from '../auth/auth.service';
import { ApiClient } from './api-client';

/**
 * Adds the user's access token to API calls. A 401 means the session is no longer valid,
 * so the user is signed out and sent to sign in, then returned to where they were.
 */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const api = inject(ApiClient);
  if (!api.isApiUrl(request.url)) return next(request);

  const auth = inject(AuthService);
  const router = inject(Router);

  return from(auth.accessToken()).pipe(
    switchMap((token) =>
      next(token ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : request),
    ),
    catchError((error: unknown) => {
      // Several calls can fail together; the first one signs out, the rest find no session.
      if (error instanceof HttpErrorResponse && error.status === 401 && auth.isSignedIn()) {
        const returnTo = router.url;
        void auth.signOut().then(() =>
          router.navigate(['/sign-in'], {
            queryParams: { next: returnTo === '/' ? null : returnTo, expired: 1 },
          }),
        );
      }
      return throwError(() => error);
    }),
  );
};
