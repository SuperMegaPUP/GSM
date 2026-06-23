/** @type {import('next').NextConfig} */
const nextConfig = {
  serverRuntimeConfig: {
    apiUrl: process.env.API_URL || "http://localhost:8000",
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
