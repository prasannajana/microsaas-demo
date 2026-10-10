# syntax=docker/dockerfile:1
# ---------- Stage 1: build the Vite app ----------
FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

# ---------- Stage 2: serve static files with unprivileged nginx (uid 101, port 8080) ----------
FROM nginxinc/nginx-unprivileged:alpine AS runtime

# Origin allowed in the CSP connect-src. Defaults to the build-time API URL; override at
# runtime with `-e API_ORIGIN=https://api.example.com` (scheme://host[:port], no path).
ARG VITE_API_URL=http://localhost:8000
ENV API_ORIGIN=${VITE_API_URL}

# The image's entrypoint renders /etc/nginx/templates/*.template into /etc/nginx/conf.d/
# with envsubst. The .inc file is not auto-included (only *.conf is); nginx.conf includes it.
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY security-headers.inc /etc/nginx/templates/security-headers.inc.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
