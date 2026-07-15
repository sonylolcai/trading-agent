/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  assetPrefix: process.env.NEXT_PUBLIC_PA_ASSET_PREFIX || undefined,
};

export default nextConfig;
