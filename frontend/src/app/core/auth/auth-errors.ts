import { isAuthError } from '@supabase/auth-js';

// Supabase's error codes, turned into messages written for people. Unknown codes fall back
// to a general message, never to Supabase's own wording.
const MESSAGES: Record<string, string> = {
  invalid_credentials: "That email and password don't match. Check them and try again.",
  email_not_confirmed: 'Confirm your email first: open the link we sent you, then sign in.',
  user_already_exists: 'An account with this email already exists. Sign in instead.',
  email_exists: 'An account with this email already exists. Sign in instead.',
  weak_password: 'Choose a stronger password: at least 8 characters, mixing letters and numbers.',
  same_password: 'Your new password must be different from the current one.',
  over_email_send_rate_limit: 'Too many emails sent. Wait a minute, then try again.',
  over_request_rate_limit: 'Too many attempts. Wait a minute, then try again.',
  email_address_invalid: "That email address doesn't look right.",
  otp_expired: 'That link has expired. Request a new one.',
  flow_state_expired: 'That link has expired. Request a new one.',
  flow_state_not_found: 'That link was already used or has expired. Request a new one.',
  signup_disabled: 'New sign-ups are closed for now.',
  provider_disabled: "That sign-in method isn't turned on yet. Use your email instead.",
  session_not_found: 'Your session ended. Please sign in again.',
};

export function describeAuthError(error: unknown): string {
  if (isAuthError(error)) {
    if (error.code && MESSAGES[error.code]) return MESSAGES[error.code];
    if (error.status === 0 || error.name === 'AuthRetryableFetchError') {
      return "We couldn't reach the sign-in service. Check your connection and try again.";
    }
  }
  return "Sign-in didn't work this time. Please try again.";
}
