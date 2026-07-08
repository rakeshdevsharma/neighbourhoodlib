"""gRPC server entrypoint."""
from __future__ import annotations

import logging
from concurrent import futures

import grpc
import library_pb2 as pb
import library_pb2_grpc as pb_grpc
from grpc_reflection.v1alpha import reflection

from .config import settings
from .servicer import LibraryServicer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("library.server")


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_LibraryServiceServicer_to_server(LibraryServicer(), server)

    # Server reflection makes the API discoverable with grpcurl / evans.
    service_names = (
        pb.DESCRIPTOR.services_by_name["LibraryService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    addr = f"[::]:{settings.grpc_port}"
    server.add_insecure_port(addr)
    server.start()
    log.info("LibraryService listening on %s", addr)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
