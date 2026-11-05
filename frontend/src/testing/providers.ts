import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import type { EnvironmentProviders, Provider } from '@angular/core';
import { provideRouter, type Routes } from '@angular/router';

import { authInterceptor } from '../app/core/api/auth.interceptor';
import { serverWakeInterceptor } from '../app/core/api/server-wake';
import { AuthService } from '../app/core/auth/auth.service';
import { APP_CONFIG } from '../app/core/config/app-config';
import { TEST_CONFIG } from './api-fixtures';
import { type FakeAuth } from './fake-auth';

/** The app's HTTP stack against a test backend, with a fake sign-in. */
export function provideTestApp(
  auth: FakeAuth,
  routes: Routes = [],
): (Provider | EnvironmentProviders)[] {
  return [
    provideRouter(routes),
    provideHttpClient(withInterceptors([serverWakeInterceptor, authInterceptor])),
    provideHttpClientTesting(),
    { provide: APP_CONFIG, useValue: TEST_CONFIG },
    { provide: AuthService, useValue: auth },
  ];
}
