/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backend = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000';
    return [{ source: '/api/:path*', destination: `${backend}/api/:path*` }];
  },
};

module.exports = nextConfig;
