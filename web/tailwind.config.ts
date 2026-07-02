import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0f1115",
        panel: "#171a21",
        panel2: "#1e222b",
        border: "#2a2f3a",
        accent: "#6ea8fe",
        critical: "#ff4d4f",
        high: "#ff9f43",
        medium: "#ffd43b",
        low: "#4dabf7",
        info: "#868e96",
      },
    },
  },
  plugins: [],
};

export default config;
