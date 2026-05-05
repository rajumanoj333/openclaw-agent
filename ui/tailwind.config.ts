import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "hsl(220 13% 9%)",
        panel: "hsl(220 13% 13%)",
        border: "hsl(220 13% 22%)",
        accent: "hsl(160 80% 45%)",
        whatsapp: "hsl(143 65% 45%)",
        voice: "hsl(265 70% 65%)",
        ui: "hsl(200 90% 60%)",
        warn: "hsl(38 92% 60%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
