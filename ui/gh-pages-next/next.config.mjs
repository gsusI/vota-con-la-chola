function normalizeBasePath(value) {
  const raw = String(value ?? "").trim();
  if (!raw || raw === "/") {
    return "";
  }
  const prefixed = raw.startsWith("/") ? raw : `/${raw}`;
  return prefixed.replace(/\/+$/u, "");
}

const basePath = normalizeBasePath(process.env.NEXT_PUBLIC_BASE_PATH ?? "");
const buildCpus = Number.parseInt(process.env.NEXT_BUILD_CPUS ?? "2", 10);
const safeBuildCpus = Number.isFinite(buildCpus) && buildCpus > 0 ? buildCpus : 2;

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  basePath,
  assetPrefix: basePath || undefined,
  images: {
    unoptimized: true,
  },
  experimental: {
    cpus: safeBuildCpus,
    staticGenerationMaxConcurrency: safeBuildCpus,
  },
};

export default nextConfig;
