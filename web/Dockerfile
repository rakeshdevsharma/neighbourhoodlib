# Build context is the repo root (see docker-compose.yml) so we can access proto/.
# ----- builder: install deps, generate grpc-web stubs, build Next.js -----
FROM node:20-bookworm AS builder
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends protobuf-compiler curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# grpc-web codegen plugin (arch-aware).
ARG GRPC_WEB_VERSION=1.5.0
ARG TARGETARCH
RUN case "${TARGETARCH}" in \
      amd64) A=x86_64 ;; \
      arm64) A=aarch64 ;; \
      *)     A=x86_64 ;; \
    esac; \
    curl -sSL -o /usr/local/bin/protoc-gen-grpc-web \
      "https://github.com/grpc/grpc-web/releases/download/${GRPC_WEB_VERSION}/protoc-gen-grpc-web-${GRPC_WEB_VERSION}-linux-${A}" \
    && chmod +x /usr/local/bin/protoc-gen-grpc-web

COPY web/package.json web/package-lock.json* ./
RUN npm install

COPY proto /proto
COPY web ./

# Generate grpc-web stubs into ./gen (library_pb.js, library_pb.d.ts, LibraryServiceClientPb.ts).
RUN mkdir -p gen && protoc \
      -I /proto/library/v1 \
      --js_out=import_style=commonjs:gen \
      --grpc-web_out=import_style=typescript,mode=grpcwebtext:gen \
      /proto/library/v1/library.proto

# NEXT_PUBLIC_* must be present at build time to be inlined into the client bundle.
ARG NEXT_PUBLIC_API_URL=http://localhost:8080
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

# ----- runner: minimal standalone Next.js server -----
FROM node:20-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
