/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontSize: {
        '3xs':      'var(--text-3xs)',
        '2xs':      'var(--text-2xs)',
        'xs-minus': 'var(--text-xs-minus)',
        'xs':       'var(--text-xs)',
        'sm':       'var(--text-sm)',
        'base':     'var(--text-md)',
        'body':     'var(--text-body)',
        'title':    'var(--text-title)',
        'lg':       'var(--text-lg)',
        'xl':       'var(--text-xl)',
        '2xl':      'var(--text-2xl)',
        'display':  'var(--text-display)',
      },
      borderRadius: {
        'xs': 'var(--radius-xs)',
        'sm': 'var(--radius-sm)',
        'md': 'var(--radius-md)',
        'lg': 'var(--radius-lg)',
        'xl': 'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
        'full': 'var(--radius-full)',
      },
      boxShadow: {
        'sm': 'var(--shadow-sm)',
        'md': 'var(--shadow-md)',
        'lg': 'var(--shadow-lg)',
      },
      colors: {
        success: 'hsl(var(--success) / <alpha-value>)',
        warn:    'hsl(var(--warn)    / <alpha-value>)',
        danger:  'hsl(var(--danger)  / <alpha-value>)',
      },
    },
  },
}
