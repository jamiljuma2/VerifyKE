import type { Config } from "tailwindcss";

/**
 * Design tokens for VerifyKE.
 *
 * Colours are deliberately anchored to meaning: the verification palette
 * (verified / suspect / failed / pending) is used consistently in the web app,
 * PDFs and emails so that a status is recognisable at a glance and never depends
 * on colour alone (icons and text labels always accompany it).
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef7f2",
          100: "#d5ebe0",
          200: "#aad7c2",
          300: "#77bd9f",
          400: "#489f7c",
          500: "#1f7a5c",
          600: "#166149",
          700: "#124d3a",
          800: "#0f3c2e",
          900: "#0b2b21",
        },
        verified: {
          DEFAULT: "#137a4a",
          soft: "#e7f5ec",
          border: "#9fd8b6",
        },
        suspect: {
          DEFAULT: "#9a6400",
          soft: "#fdf3e2",
          border: "#f0cd93",
        },
        failed: {
          DEFAULT: "#a3221a",
          soft: "#fdeceb",
          border: "#f0b3ae",
        },
        muted: {
          DEFAULT: "#5b6470",
          soft: "#f4f5f7",
          border: "#dfe2e7",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      maxWidth: {
        prose: "68ch",
      },
    },
  },
  plugins: [],
};

export default config;
