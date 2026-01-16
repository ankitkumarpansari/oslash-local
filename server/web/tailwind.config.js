/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['SF Mono', 'Menlo', 'monospace'],
      },
      fontSize: {
        'xxs': '11px',
        'xs': '12px',
        'sm': '13px',
        'base': '14px',
        'lg': '15px',
        'xl': '16px',
      },
      colors: {
        bg: {
          DEFAULT: '#0a0a0a',
          secondary: '#111',
          tertiary: '#171717',
          hover: '#1a1a1a',
        },
        border: {
          DEFAULT: '#222',
          light: '#1a1a1a',
        },
        text: {
          DEFAULT: '#fafafa',
          secondary: '#888',
          tertiary: '#555',
        },
      },
      borderRadius: {
        'sm': '4px',
        'md': '6px',
        'lg': '8px',
      },
      animation: {
        'fade-in': 'fadeIn 0.15s ease-out',
        'slide-up': 'slideUp 0.2s ease-out forwards',
      },
    },
  },
  plugins: [],
}
