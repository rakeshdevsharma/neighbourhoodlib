/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server bundle for the Docker runner stage.
  output: "standalone",
  // Generated grpc-web stubs shouldn't block the build on lint.
  eslint: { ignoreDuringBuilds: true },
};

module.exports = nextConfig;
