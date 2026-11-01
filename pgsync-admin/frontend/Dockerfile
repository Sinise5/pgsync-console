# ==========================================
# PGSync Admin Frontend - Self-contained build
# Context: pgsync-admin/frontend/
# ==========================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy source (relative to context = pgsync-admin/frontend/)
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html ./
COPY src ./src
COPY vite.config.ts ./
COPY tsconfig.json ./
COPY tailwind.config.cjs postcss.config.cjs ./

# Build static assets
RUN npm run build

# Nginx stage
FROM nginx:alpine

WORKDIR /usr/share/nginx/html

COPY nginx.conf /etc/nginx/nginx.conf

COPY --from=builder /app/dist .

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
