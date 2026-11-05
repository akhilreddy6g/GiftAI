import { InjectionToken, inject } from '@angular/core';
import { AuthClient, type GoTrueClient } from '@supabase/auth-js';

import { APP_CONFIG } from '../config/app-config';

/**
 * Supabase's auth client alone, without the database, storage and realtime clients the
 * full SDK bundles: GiftAI uses Supabase for sign-in only. Null when this build has no
 * Supabase settings.
 */
export const AUTH_CLIENT = new InjectionToken<GoTrueClient | null>('AUTH_CLIENT', {
  providedIn: 'root',
  factory: () => {
    const { supabaseUrl, supabaseAnonKey } = inject(APP_CONFIG);
    if (!supabaseUrl || !supabaseAnonKey) return null;
    return new AuthClient({
      url: `${supabaseUrl}/auth/v1`,
      headers: { apikey: supabaseAnonKey, Authorization: `Bearer ${supabaseAnonKey}` },
      storageKey: 'giftai-auth',
      // PKCE keeps tokens out of URLs: links and redirects carry a one-time code instead.
      flowType: 'pkce',
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    });
  },
});
