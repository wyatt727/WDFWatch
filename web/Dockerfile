# Dockerfile for WDFWatch Web UI
# Multi-stage build for Next.js application

# Stage 1: Dependencies
FROM node:20-slim AS deps
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./
RUN npm ci

# Stage 2: Builder
FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Install OpenSSL for Prisma generation
RUN apt-get update -qq && \
    apt-get install -y openssl && \
    rm -rf /var/lib/apt/lists/*

# Generate Prisma client with the correct binary target for Debian
ENV PRISMA_CLI_BINARY_TARGETS=debian-openssl-3.0.x
RUN npx prisma generate

# Build Next.js application
ENV NEXT_TELEMETRY_DISABLED 1
RUN npm run build

# Stage 3: Runner
FROM node:20-slim AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

# Install OpenSSL and Python (needed for mounted scripts)
RUN apt-get update -qq && \
    apt-get install -y openssl python3 python3-pip curl && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1001 nodejs
RUN useradd --system --uid 1001 --gid nodejs nextjs

# Copy necessary files
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Copy Prisma files
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder /app/node_modules/@prisma ./node_modules/@prisma

USER nextjs

EXPOSE 8888

ENV PORT 8888

CMD ["node", "server.js"]