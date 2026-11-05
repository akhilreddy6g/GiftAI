# GiftAI frontend

The Angular app: sign-in, the chat list, and conversations with the gift assistant.

Each reply that suggests gifts shows them as cards under it: the product photo, its 2023
price and rating, why it suits the person and the gifting rules behind it, links to view it
or add it to the Amazon cart (one at a time or all at once), and thumbs up or down. After
someone opens a product and comes back to the tab, the card asks "Did you find it on
Amazon?", and products most people couldn't find are ranked lower for everyone.

## Running it

Requires Node 22.12 or newer, and the API running (see the root README).

```bash
npm install
npm start          # http://localhost:4200
```

Settings come from environment variables, or from the repository's root `.env` (the same
file the backend reads). `npm start`, `npm run build` and `npm test` write them into the
app first, with `scripts/write-config.mjs`:

| Variable            | Meaning                                                |
| ------------------- | ------------------------------------------------------ |
| `GIFTAI_API_URL`    | Where the API lives (default `http://localhost:8000`)  |
| `SUPABASE_URL`      | The Supabase project URL                               |
| `SUPABASE_ANON_KEY` | The Supabase anon / publishable key (public by design) |

Without the Supabase values the app still builds, and the sign-in page says that sign-in
isn't set up. The API must allow the app's origin in `CORS_ALLOWED_ORIGINS`.

## Setting up sign-in

GiftAI uses Supabase only to sign people in. In the Supabase dashboard, once per project:

1. **Authentication > URL Configuration.** Set the Site URL to where the app runs
   (`http://localhost:4200` locally), and add `http://localhost:4200/auth/callback` to the
   Redirect URLs (plus the deployed site's `/auth/callback` later). Google sign-in, email
   links and password-reset links all return there.
2. **Authentication > Sign In / Providers > Google** (optional). Turn it on with a client ID
   and secret from a free Google Cloud OAuth client whose authorized redirect URI is the
   callback URL Supabase shows on that page. Without it, the Google button reports that the
   method isn't turned on, and email sign-in still works.

Email and password sign-up and email links work out of the box. Supabase's built-in email
sender is limited to a few emails an hour, which is fine for testing.

## Checks

```bash
npm run lint           # ESLint, including angular-eslint's accessibility rules
npm run format:check   # Prettier
npm test               # unit tests (Vitest)
npm run build          # production build into dist/frontend/browser
```

CI also runs Lighthouse on the built site and fails below 0.95 for accessibility and 0.9
for performance and best practices (`lighthouserc.json`).

## The API contract

`src/app/core/api/schema.ts` is generated from the backend's OpenAPI schema, so a change to
the API's shape breaks the build here instead of failing at runtime. After changing the API:

```bash
npm run api:sync   # exports openapi.json from ../backend (needs uv), regenerates the types
```

CI regenerates both files and fails if the committed copies differ.

## Layout

```
src/app/core/       app-wide pieces: API client and types, sign-in, theme, shared UI
src/app/features/   pages: auth (sign-in, callback, reset), shell (sidebar, drawer), chats
src/testing/        fakes and fixtures for unit tests
```

Pages are standalone components with OnPush change detection, state lives in signals, and
every page is lazy loaded.

## Docker

`docker compose up --build` from the repository root builds this app with the `.env`
Supabase settings and serves it on http://localhost:4200 with nginx. Vercel builds the
deployed site from `npm run build` (`vercel.json`).
