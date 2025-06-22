import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://dashboard-backend:8000/api/:path*',
      },
    ]
  },
};

export default nextConfig;
