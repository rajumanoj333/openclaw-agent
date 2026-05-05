/** @type {import('next').NextConfig} */
const nextConfig = {
  // Off in dev so useEffect doesn't double-fire and cause two WebSocket
  // connections (which led to duplicate inbound messages in the chat feed).
  reactStrictMode: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.ngrok-free.dev" },
      { protocol: "https", hostname: "**.ngrok.app" },
      { protocol: "https", hostname: "**.cloudapp.azure.com" },
    ],
  },
};

export default nextConfig;
