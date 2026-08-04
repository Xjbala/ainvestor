/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'system-ui', '-apple-system', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
                mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
            },
            boxShadow: {
                'rams': '0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.1)',
                'rams-elevated': '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)',
            },
            animation: {
                'data-flow': 'dataFlow 15s ease infinite',
                'pulse-glow': 'pulse-glow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'breathe': 'breathe 3s ease-in-out infinite',
                'flow': 'flow 1s linear infinite',
            },
            keyframes: {
                dataFlow: {
                    '0%': { backgroundPosition: '0% 50%' },
                    '50%': { backgroundPosition: '100% 50%' },
                    '100%': { backgroundPosition: '0% 50%' },
                },
                'pulse-glow': {
                    '0%, 100%': { opacity: '0.4' },
                    '50%': { opacity: '1' },
                },
                breathe: {
                    '0%, 100%': { boxShadow: '0 0 0 0 rgba(0, 217, 255, 0.1)' },
                    '50%': { boxShadow: '0 0 20px 5px rgba(0, 217, 255, 0.2)' },
                },
                flow: {
                    '0%': { backgroundPosition: '0 0' },
                    '100%': { backgroundPosition: '40px 0' },
                },
            },
            keyframes: {
                dataFlow: {
                    '0%': { backgroundPosition: '0% 50%' },
                    '50%': { backgroundPosition: '100% 50%' },
                    '100%': { backgroundPosition: '0% 50%' },
                },
                'pulse-glow': {
                    '0%, 100%': { opacity: '0.4' },
                    '50%': { opacity: '1' },
                },
                breathe: {
                    '0%, 100%': { boxShadow: '0 0 0 0 rgba(0, 217, 255, 0.1)' },
                    '50%': { boxShadow: '0 0 20px 5px rgba(0, 217, 255, 0.2)' },
                },
                flow: {
                    '0%': { backgroundPosition: '0 0' },
                    '100%': { backgroundPosition: '40px 0' },
                },
            },
        },
    },
    plugins: [
        require('tailwindcss-typography'),
    ],
}
