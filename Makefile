# Convenience targets for local development, codegen, testing, and Docker ops.
.PHONY: help up down logs build push proto-py proto-web seed test psql clean

help:
	@echo "Targets:"
	@echo "  up         - start services (use local images, pull from registry if missing)"
	@echo "  down       - stop all services"
	@echo "  logs       - tail logs"
	@echo "  build      - rebuild server and web images (does not start containers)"
	@echo "  push       - build and push server/web images (set IMAGE_REGISTRY)"
	@echo "  proto-py   - generate Python gRPC stubs into server/gen (local dev)"
	@echo "  proto-web  - generate grpc-web stubs into web/gen (local dev)"
	@echo "  seed       - seed sample data into a running server"
	@echo "  test       - run backend unit/integration tests (needs a Postgres)"
	@echo "  psql       - open a psql shell to the running db"
	@echo "  clean      - down + remove volumes and generated stubs"

up:
	docker compose up --no-build --pull missing

push:
	docker compose build server web
	docker compose push server web

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

proto-py:
	cd server && bash scripts/gen_proto.sh

proto-web:
	mkdir -p web/gen && protoc -I /usr/include -I proto/library/v1 \
	  --js_out=import_style=commonjs:web/gen \
	  --grpc-web_out=import_style=typescript,mode=grpcwebtext:web/gen \
	  proto/library/v1/library.proto

seed:
	docker compose exec server python -m app.scripts.seed

test:
	cd server && python -m pytest -v

psql:
	docker compose exec db psql -U library -d library

clean:
	docker compose down -v
	rm -rf server/gen web/gen web/.next
