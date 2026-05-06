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
        "accent-soft": "hsl(var(--accent-soft))",
        "accent-glow": "hsl(var(--accent-glow))",
        whatsapp: "hsl(143 72% 45%)",
        voice: "hsl(265 65% 60%)",
        ui: "hsl(200 80% 52%)",
        warn: "hsl(38 92% 52%)",
        danger: "hsl(0 75% 55%)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        xl: "16px",
        "2xl": "20px",
        "3xl": "24px",
      },
      boxShadow: {
        card: "0 1px 2px hsl(220 30% 10% / 0.04), 0 8px 24px hsl(220 30% 10% / 0.05)",
        soft: "0 1px 3px hsl(220 30% 10% / 0.06)",
      },
    },
  },
  plugins: [],
} satisfies Config;
