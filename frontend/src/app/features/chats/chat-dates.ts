const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * A short label for when a chat was last active: the time today, the weekday this past
 * week, and the date before that (with the year once it isn't this year).
 */
export function formatChatDate(iso: string, now = new Date(), locale?: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (date.getTime() >= startOfToday) {
    return date.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' });
  }
  if (date.getTime() >= startOfToday - 6 * DAY_MS) {
    return date.toLocaleDateString(locale, { weekday: 'short' });
  }
  return date.toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: 'numeric' }),
  });
}

/** A date-only value from the API ("2026-12-14") in words, without timezone shifts. */
export function formatPlainDate(value: string, locale?: string): string {
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Date(year, month - 1, day).toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}
