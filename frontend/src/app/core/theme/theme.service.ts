import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject, signal } from '@angular/core';

export type ThemePreference = 'system' | 'light' | 'dark';

export const THEME_STORAGE_KEY = 'giftai-theme';

/**
 * Light, dark or follow the device. The choice is remembered in this browser; an inline
 * script in index.html applies it before the first paint so the page never flashes.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly media = this.document.defaultView?.matchMedia?.('(prefers-color-scheme: dark)');
  private readonly systemPrefersDark = signal(this.media?.matches ?? false);

  readonly preference = signal<ThemePreference>(readStoredPreference());

  constructor() {
    this.media?.addEventListener('change', (event) => this.systemPrefersDark.set(event.matches));
    effect(() => {
      const preference = this.preference();
      const dark = preference === 'dark' || (preference === 'system' && this.systemPrefersDark());
      const root = this.document.documentElement;
      root.classList.toggle('dark', dark);
      root.style.colorScheme = dark ? 'dark' : 'light';
      writeStoredPreference(preference);
    });
  }

  set(preference: ThemePreference): void {
    this.preference.set(preference);
  }
}

function readStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return stored === 'light' || stored === 'dark' ? stored : 'system';
  } catch {
    return 'system';
  }
}

function writeStoredPreference(preference: ThemePreference): void {
  try {
    if (preference === 'system') localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Storage can be blocked (private windows); the choice then lasts for this visit.
  }
}
