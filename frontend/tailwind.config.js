/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        fss: {
          bronze:      '#B5845A',
          'bronze-light': '#D4A373',
          'bronze-dark':  '#8B5E3C',
        },
        sidebar: {
          DEFAULT: '#1A2035',
          hover:   '#252F4A',
          active:  '#2F3D5C',
        },
      },
    },
  },
  plugins: [],
}
