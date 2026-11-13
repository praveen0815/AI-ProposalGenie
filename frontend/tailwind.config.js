/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 18px 40px rgba(2, 8, 20, 0.28)",
      },
    },
  },
  plugins: [],
};
