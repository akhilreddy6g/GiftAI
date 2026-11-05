import { TestBed } from '@angular/core/testing';

import { THEME_STORAGE_KEY, ThemeService } from './theme.service';

describe('ThemeService', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('applies and remembers an explicit choice', () => {
    const theme = TestBed.inject(ThemeService);

    theme.set('dark');
    TestBed.tick();

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');

    theme.set('light');
    TestBed.tick();

    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.style.colorScheme).toBe('light');
  });

  it('forgets the choice when following the device again', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    const theme = TestBed.inject(ThemeService);
    expect(theme.preference()).toBe('dark');

    theme.set('system');
    TestBed.tick();

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  });
});
