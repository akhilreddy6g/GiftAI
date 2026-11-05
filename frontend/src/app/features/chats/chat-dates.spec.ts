import { formatChatDate, formatPlainDate } from './chat-dates';

describe('formatChatDate', () => {
  const now = new Date(2026, 10, 5, 15, 0); // Thu Nov 5 2026, 3 PM local time

  it('shows the time for today', () => {
    expect(formatChatDate(new Date(2026, 10, 5, 9, 30).toISOString(), now, 'en-US')).toBe(
      '9:30 AM',
    );
  });

  it('shows the weekday within the past week', () => {
    expect(formatChatDate(new Date(2026, 10, 2, 9, 0).toISOString(), now, 'en-US')).toBe('Mon');
  });

  it('shows the date before that, adding the year only for other years', () => {
    expect(formatChatDate(new Date(2026, 9, 1).toISOString(), now, 'en-US')).toBe('Oct 1');
    expect(formatChatDate(new Date(2025, 9, 1).toISOString(), now, 'en-US')).toBe('Oct 1, 2025');
  });

  it('returns nothing for an invalid date', () => {
    expect(formatChatDate('not a date', now)).toBe('');
  });
});

describe('formatPlainDate', () => {
  it('formats a date-only value without shifting the day', () => {
    expect(formatPlainDate('2026-12-14', 'en-US')).toBe('Dec 14, 2026');
  });
});
