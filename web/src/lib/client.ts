"use client";

// Thin wrapper around the generated grpc-web client. The browser talks
// gRPC-Web to Envoy (NEXT_PUBLIC_API_URL), which forwards native gRPC to the
// Python server.
import { LibraryServiceClient } from "@gen/LibraryServiceClientPb";
import * as pb from "@gen/library_pb";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export const client = new LibraryServiceClient(API_URL, null, null);
export { pb };

// grpc-web surfaces errors as { code, message }. Normalize to an Error.
export function grpcMessage(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) {
    return String((err as { message: unknown }).message);
  }
  return String(err);
}
