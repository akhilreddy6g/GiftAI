import { InjectionToken } from '@angular/core';

import { APP_CONFIG_VALUES } from './app-config.values';

/** Deployment-specific settings, written at build time by scripts/write-config.mjs. */
export interface AppConfig {
  /** The API's origin, without a trailing slash. */
  readonly apiUrl: string;
  /** Empty when sign-in isn't set up for this build. */
  readonly supabaseUrl: string;
  readonly supabaseAnonKey: string;
}

export const APP_CONFIG = new InjectionToken<AppConfig>('APP_CONFIG', {
  providedIn: 'root',
  factory: () => APP_CONFIG_VALUES,
});
