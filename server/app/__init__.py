"""Neighbourhood Library backend application package.

Layers (outer → inner):
  api/grpc   — gRPC transport, maps proto ↔ domain
  books, members, lending — business logic (services)
  persistence  — SQLAlchemy ORM and database sessions
  core         — config, enums, validation, shared errors
"""
