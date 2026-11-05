/** Supabase's default minimum; bcrypt reads at most 72 bytes, so longer adds nothing. */
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_LENGTH = 72;
