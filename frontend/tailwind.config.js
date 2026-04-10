/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        fss: {
          navy:           '#0B1F3A',
          'navy-light':   '#1A2F50',
          'navy-dark':    '#071428',
          bronze:         '#C89B3C',
          'bronze-light': '#D4AF6A',
          'bronze-dark':  '#A07828',
        },
        sidebar: {
          DEFAULT: '#0B1F3A',
          hover:   '#1A2F50',
          active:  '#243D6A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Cairo', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
