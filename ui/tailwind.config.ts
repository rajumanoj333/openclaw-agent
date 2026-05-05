import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "hsl(var(--bg))",
        "bg-elev": "hsl(var(--bg-elev))",
        panel: "hsl(var(--panel))",
        border: "hsl(var(--border))",
        "border-strong": "hsl(var(--border-strong))",
        text: "hsl(var(--text))",
        "text-dim": "hsl(var(--text-dim))",
        "text-mute": "hsl(var(--text-mute))",
        accent: "hsl(var(--accent))",
        "accent-dim": "hsl(var(--accent-dim))",
        whatsapp: "hsl(143 70% 50%)",
        voice: "hsl(265 70% 65%)",
        ui: "hsl(200 90% 60%)",
        warn: "hsl(38 92% 60%)",
        danger: "hsl(0 80% 60%)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px hsl(var(--accent) / 0.4), 0 8px 30px hsl(var(--accent) / 0.18)",
      },
    },
  },
  plugins: [],
} satisfies Config;
