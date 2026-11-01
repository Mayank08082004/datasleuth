/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        amber: { DEFAULT: "#F5BC42" },
        canvas: "#FAF8F2",
        ink: "#111111",
        muted: "#777166",
        line: "#E9E4D8",
        sage: { DEFAULT: "#6F8F72", soft: "#E6EEE3" },
        rose: { DEFAULT: "#B5767A", soft: "#F4E4E4" },
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', '"EB Garamond"', "Georgia", "serif"],
        sans: ['"Nunito Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: { card: "0 1px 2px rgba(17,17,17,0.04), 0 4px 12px rgba(17,17,17,0.04)" },
    },
  },
  plugins: [],
};
