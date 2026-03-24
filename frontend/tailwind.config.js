/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Syne"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
        body: ['"DM Sans"', 'sans-serif'],
      },
      colors: {
        void: '#080B14',
        surface: '#0D1220',
        panel: '#111827',
        border: '#1E2D45',
        accent: '#00E5FF',
        'accent-dim': '#0097A7',
        plasma: '#7C3AED',
        danger: '#FF3B5C',
        warn: '#FFB800',
        success: '#00E676',
        muted: '#4B5E7A',
        text: '#C8D8F0',
        'text-dim': '#8899AA',
      },
      boxShadow: {
        'glow-accent': '0 0 20px rgba(0, 229, 255, 0.15)',
        'glow-danger': '0 0 20px rgba(255, 59, 92, 0.15)',
        'glow-success': '0 0 20px rgba(0, 230, 118, 0.15)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in': 'slideIn 0.4s ease-out',
        'fade-up': 'fadeUp 0.5s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(-20px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeUp: {
          '0%': { transform: 'translateY(16px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
