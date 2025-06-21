import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Only use static export for production builds
  ...(process.env.NODE_ENV === 'production' && {
    output: 'export',
    trailingSlash: true,
    images: {
      unoptimized: true,
    },
  }),
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
