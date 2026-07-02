/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Severidades — legíveis sobre fundo escuro (refinadas em index.css).
        sev: {
          critical: '#f87171',
          high: '#fb923c',
          medium: '#facc15',
          low: '#60a5fa',
          info: '#94a3b8',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
