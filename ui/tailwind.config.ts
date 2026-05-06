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
        ink: "hsl(var(--ink))",
        text: "hsl(var(--text))",
        "text-dim": "hsl(var(--text-dim))",
        "text-mute": "hsl(var(--text-mute))",
        accent: "hsl(var(--accent))",
        "accent-soft": "hsl(var(--accent-soft))",
        "accent-glow": "hsl(var(--accent-glow))",
        whatsapp: "hsl(143 65% 38%)",
        voice: "hsl(265 55% 52%)",
        ui: "hsl(212 75% 48%)",
        warn: "hsl(28 88% 46%)",
        danger: "hsl(0 70% 48%)",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        xl: "16px",
        "2xl": "20px",
        "3xl": "24px",
      },
      boxShadow: {
        card: "0 1px 2px hsl(220 30% 10% / 0.04), 0 12px 32px hsl(220 30% 10% / 0.06)",
        soft: "0 1px 3px hsl(220 30% 10% / 0.08)",
        ink: "0 6px 18px hsl(220 30% 10% / 0.18)",
      },
      letterSpacing: {
        tightest: "-0.03em",
        editorial: "-0.025em",
      },
    },
  },
  plugins: [],
} satisfies Config;
