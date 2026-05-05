/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.ngrok-free.dev" },
      { protocol: "https", hostname: "**.ngrok.app" },
      { protocol: "https", hostname: "**.cloudapp.azure.com" },
    ],
  },
};

export default nextConfig;
