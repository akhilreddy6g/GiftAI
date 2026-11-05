/**
 * Returns ``next`` when it is a path inside this app, and "/" otherwise, so a crafted
 * sign-in link can't send someone to another site after they sign in.
 */
export function safeRedirect(next: string | null | undefined): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.includes('\\')) {
    return '/';
  }
  // Reject anything the URL parser resolves outside this origin.
  const base = 'https://giftai.invalid';
  try {
    const url = new URL(next, base);
    return url.origin === base ? `${url.pathname}${url.search}${url.hash}` : '/';
  } catch {
    return '/';
  }
}
