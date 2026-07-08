#!/usr/bin/env bash
# Generate Python gRPC stubs from the .proto into server/gen/.
# Run from the repo root (or anywhere; paths are resolved relative to this script).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$SERVER_DIR")"
PROTO_DIR="$REPO_ROOT/proto/library/v1"
OUT_DIR="$SERVER_DIR/gen"

mkdir -p "$OUT_DIR"

python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$OUT_DIR" \
  --grpc_python_out="$OUT_DIR" \
  --pyi_out="$OUT_DIR" \
  "$PROTO_DIR/library.proto"

echo "Generated stubs in $OUT_DIR"
