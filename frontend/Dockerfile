# Builds the static site, then serves it with an unprivileged nginx.
#   docker build -t giftai-frontend --build-arg SUPABASE_URL=... --build-arg SUPABASE_ANON_KEY=... .
# The values below are public by design (the anon key is a publishable key), so build
# arguments are fine for them. Vercel builds the deployed site itself from `npm run build`.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG GIFTAI_API_URL=http://localhost:8000
ARG SUPABASE_URL=
ARG SUPABASE_ANON_KEY=
ENV GIFTAI_API_URL=$GIFTAI_API_URL SUPABASE_URL=$SUPABASE_URL SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/ > /dev/null || exit 1
