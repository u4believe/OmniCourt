import type { NextConfig } from "next";

// GitHub Pages serves this repo at /OmniCourt, Vercel and Netlify serve it at
// the root. NEXT_PUBLIC_BASE_PATH lets one build config cover both, and keeps
// `npm run dev` at the root locally where it is unset.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The whole app is client-rendered and talks straight to Studio Next, so it
  // needs no server at runtime. Exporting plain files means any static host
  // can serve it and there is no remote build step to misconfigure.
  output: "export",
  basePath,
  assetPrefix: basePath || undefined,
  images: { unoptimized: true },
  turbopack: {},
};

export default nextConfig;
