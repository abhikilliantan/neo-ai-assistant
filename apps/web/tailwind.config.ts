import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

// darkMode via the same data-theme attribute next-themes sets, so any dark:
// utility still resolves. The token system flips values through CSS variables,
// so most styling is theme-agnostic and dark: is rarely needed.
const config: Config = {
  darkMode: ["selector", ':root[data-theme="dark"]'],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "1rem" },
    extend: {
      colors: {
        // shadcn semantic — the `/ <alpha-value>` slot makes opacity modifiers
        // (bg-primary/90, bg-success/15, border-danger/40) resolve correctly.
        border: "hsl(var(--border) / <alpha-value>)",
        input: "hsl(var(--input) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        primary: {
          DEFAULT: "hsl(var(--primary) / <alpha-value>)",
          foreground: "hsl(var(--primary-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT: "hsl(var(--muted) / <alpha-value>)",
          foreground: "hsl(var(--muted-foreground) / <alpha-value>)",
        },
        card: {
          DEFAULT: "hsl(var(--card) / <alpha-value>)",
          foreground: "hsl(var(--card-foreground) / <alpha-value>)",
        },
        // design tokens
        accent: "hsl(var(--accent) / <alpha-value>)",
        "on-accent": "hsl(var(--on-accent) / <alpha-value>)",
        faint: "hsl(var(--faint) / <alpha-value>)",
        success: "hsl(var(--success) / <alpha-value>)",
        warn: "hsl(var(--warn) / <alpha-value>)",
        danger: "hsl(var(--danger) / <alpha-value>)",
        // translucent glass surfaces (already carry alpha; used via bg-glass etc.)
        glass: "var(--glass)",
        "glass-2": "var(--glass-2)",
        "glass-hi": "var(--glass-hi)",
        "glass-border": "var(--glass-border)",
        "glass-border-strong": "var(--glass-border-strong)",
        // redesign (Phase 0) — dark AI-OS scale, namespaced so it can't collide
        // with the semantic tokens above or affect any existing page.
        rd: {
          base: "hsl(var(--rd-base) / <alpha-value>)",
          panel: "hsl(var(--rd-panel) / <alpha-value>)",
          card: "hsl(var(--rd-card) / <alpha-value>)",
          border: "var(--rd-border)",
          "border-hover": "var(--rd-border-hover)",
          cyan: "hsl(var(--rd-cyan) / <alpha-value>)",
          "cyan-2": "hsl(var(--rd-cyan-2) / <alpha-value>)",
          violet: "hsl(var(--rd-violet) / <alpha-value>)",
          "violet-2": "hsl(var(--rd-violet-2) / <alpha-value>)",
          green: "hsl(var(--rd-green) / <alpha-value>)",
          amber: "hsl(var(--rd-amber) / <alpha-value>)",
          rose: "hsl(var(--rd-rose) / <alpha-value>)",
          heading: "hsl(var(--rd-heading) / <alpha-value>)",
          body: "hsl(var(--rd-body) / <alpha-value>)",
          muted: "hsl(var(--rd-muted) / <alpha-value>)",
        },
      },
      backgroundImage: {
        "accent-grad": "var(--accent-grad)",
        "app-bg": "var(--app-bg)",
        "rd-grad": "var(--rd-grad)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        card: "var(--radius-card)",
        control: "var(--radius-control)",
      },
      boxShadow: {
        glow: "0 0 0 1px var(--glass-border-strong), 0 10px 40px -12px var(--glow)",
        "glow-ring": "0 0 0 3px var(--glow)",
      },
    },
  },
  plugins: [animate],
};

export default config;
