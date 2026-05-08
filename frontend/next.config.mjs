/** @type {import('next').NextConfig} */
const nextConfig = {
  // Bake a build timestamp and version into the client bundle.
  // On local dev this resets when the dev server restarts.
  // On Vercel this is set at build time — reload the page on your phone to get the new build.
  env: {
    NEXT_PUBLIC_BUILD_TIME: new Date().toISOString(),
    NEXT_PUBLIC_APP_VERSION: "0.1.0",
  },

  async rewrites() {
    if (process.env.NEXT_PUBLIC_API_URL) return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
