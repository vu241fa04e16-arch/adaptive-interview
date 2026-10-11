/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0a0d14',
        surface: {
          50: '#1e2638',
          100: '#171e2e',
          200: '#121824',
          300: '#0d121c',
          DEFAULT: '#111726',
        },
        border: '#1e293b',
        cyber: {
          blue: '#38bdf8',
          cyan: '#06b6d4',
          indigo: '#6366f1',
          purple: '#a855f7',
          pink: '#ec4899',
        },
        integrity: {
          safe: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
          neutral: '#64748b',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'soundwave': 'soundwave 1.2s ease-in-out infinite alternate',
        'glow': 'glow 2.5s ease-in-out infinite alternate',
      },
      keyframes: {
        soundwave: {
          '0%': { height: '15%' },
          '100%': { height: '100%' },
        },
        glow: {
          '0%': { boxShadow: '0 0 15px rgba(99, 102, 241, 0.3)' },
          '100%': { boxShadow: '0 0 30px rgba(6, 182, 212, 0.6)' },
        }
      }
    },
  },
  plugins: [],
}
