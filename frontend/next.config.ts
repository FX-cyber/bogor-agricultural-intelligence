import type { NextConfig } from 'next';
const pages = process.env.DEPLOY_TARGET === 'github-pages';
const apiOrigin = process.env.NEXT_PUBLIC_API_BASE_URL;
if (pages && (!apiOrigin || !/^https:\/\/[^/]+$/.test(apiOrigin))) {
  throw new Error('GitHub Pages requires NEXT_PUBLIC_API_BASE_URL: an HTTPS backend origin without a trailing slash.');
}
const config: NextConfig = pages ? {
  output: 'export',
  distDir: '.next-pages',
  trailingSlash: true,
  basePath: process.env.PAGES_BASE_PATH || '',
  images: { unoptimized: true },
} : {
  async rewrites() { return [{ source: '/api/:path*', destination: 'http://127.0.0.1:8000/api/:path*' }]; },
};
export default config;
