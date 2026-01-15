/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{ts,tsx,html}"],
  theme: {
    extend: {
      // Fixed z-index scale (UI Skills constraint)
      zIndex: {
        base: "0",
        dropdown: "10",
        modal: "20",
        toast: "30",
        overlay: "9999",
      },
    },
  },
  plugins: [],
};

