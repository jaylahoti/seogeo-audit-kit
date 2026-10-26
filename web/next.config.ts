import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone", // small self-contained server for the Docker image
};

export default nextConfig;
