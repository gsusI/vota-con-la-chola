const defaultBasePath = process.env.NODE_ENV === "development" ? "" : "/vota-con-la-chola";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || defaultBasePath;

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  basePath,
  assetPrefix: basePath || undefined,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
