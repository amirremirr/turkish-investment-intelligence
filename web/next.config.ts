import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // The Supabase serving DB is a small (nano) instance behind a
    // connection pooler. Next's default build fans out to ~9 worker
    // processes that render pages concurrently, which overwhelms the
    // instance and trips its statement timeout. Force a single worker
    // and cap concurrent page renders so build-time queries stay
    // within what the pooler comfortably serves.
    staticGenerationMinPagesPerWorker: 1000,
    staticGenerationMaxConcurrency: 2,
  },
};

export default nextConfig;
