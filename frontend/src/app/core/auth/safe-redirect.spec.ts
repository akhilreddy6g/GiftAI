import { safeRedirect } from './safe-redirect';

describe('safeRedirect', () => {
  it.each([
    ['/chats/abc', '/chats/abc'],
    ['/chats/abc?tab=1#end', '/chats/abc?tab=1#end'],
    ['/reset-password', '/reset-password'],
  ])('keeps the in-app path %s', (next, expected) => {
    expect(safeRedirect(next)).toBe(expected);
  });

  it.each([
    null,
    undefined,
    '',
    'https://evil.example',
    '//evil.example/path',
    '/\\evil.example',
    'javascript:alert(1)',
    'chats/abc',
  ])('sends %s home instead', (next) => {
    expect(safeRedirect(next)).toBe('/');
  });
});
