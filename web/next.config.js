/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Generated grpc-web stubs shouldn't block the build on lint.
  eslint: { ignoreDuringBuilds: true },
};

module.exports = nextConfig;
