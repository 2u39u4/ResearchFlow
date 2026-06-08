import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        primary: "#FF4B4B",
        background: "#FFFFFF",
        surface: "#F0F2F6",
        foreground: "#31333F",
        verified: "#D4EDDA",
        "not-found": "#F8D7DA",
        mismatch: "#FFF3CD",
        warning: "#FFF3CD",
      },
      borderRadius: {
        DEFAULT: "8px",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
