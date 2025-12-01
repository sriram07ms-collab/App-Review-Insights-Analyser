import type { NextConfig } from "next";

// For GitHub Pages project sites, we need basePath
// Repository name: Milestone-2
// GitHub Pages URL: https://sriram07ms-collab.github.io/Milestone-2/
const basePath = '/Milestone-2';

const nextConfig: NextConfig = {
  output: 'export',  // Enable static export for GitHub Pages
  basePath: basePath,  // Required for GitHub Pages project sites
  images: {
    unoptimized: true,  // Required for static export
  },
  trailingSlash: true,  // Better compatibility with GitHub Pages
};

export default nextConfig;
