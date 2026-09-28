import type { NextConfig } from 'next';
const pages = process.env.DEPLOY_TARGET === 'github-pages';
const config: NextConfig = pages ? {
  env: { NEXT_PUBLIC_STATIC_MODE: 'true', NEXT_PUBLIC_BASE_PATH: process.env.PAGES_BASE_PATH || '' },
  output: 'export',
  distDir: '.next-pages',
  trailingSlash: true,
  basePath: process.env.PAGES_BASE_PATH || '',
  images: { unoptimized: true },
} : {
  async rewrites() { return [{ source: '/api/:path*', destination: 'http://127.0.0.1:8000/api/:path*' }]; },
};
export default config;
