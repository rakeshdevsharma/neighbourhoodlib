"""Transport adapters that expose the domain over the wire.

The gRPC servicer delegates to service modules; mappers translate between
protobuf messages and SQLAlchemy models without leaking transport types inward.
"""
