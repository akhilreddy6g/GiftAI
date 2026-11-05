import { inject } from '@angular/core';
import { type CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';
import { safeRedirect } from './safe-redirect';

/** Lets signed-in users through and sends everyone else to sign in, then back here. */
export const requireSignIn: CanActivateFn = async (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  await auth.ready;
  if (auth.isSignedIn()) return true;
  const next = state.url === '/' ? null : state.url;
  return router.createUrlTree(['/sign-in'], { queryParams: next ? { next } : {} });
};

/** Keeps signed-in users off the sign-in page. */
export const requireSignedOut: CanActivateFn = async (route) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  await auth.ready;
  if (!auth.isSignedIn()) return true;
  return router.parseUrl(safeRedirect(route.queryParamMap.get('next')));
};
