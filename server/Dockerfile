# Build context is the repo root (see docker-compose.yml) so we can access proto/.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/app/gen

WORKDIR /app

COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Proto contract + server source.
COPY proto /proto
COPY server /app

# Generate gRPC stubs into /app/gen (flat: library_pb2, library_pb2_grpc).
RUN mkdir -p /app/gen && \
    python -m grpc_tools.protoc \
      -I /proto/library/v1 \
      --python_out=/app/gen \
      --grpc_python_out=/app/gen \
      --pyi_out=/app/gen \
      /proto/library/v1/library.proto && \
    chmod +x /app/scripts/*.sh

EXPOSE 50051

CMD ["/app/scripts/entrypoint.sh"]
