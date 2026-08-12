/** @type {import('tailwindcss').Config} */
// Golden Time 设计系统映射：颜色/字体/圆角统一走 CSS 变量 token（见 src/styles/design-tokens.css）
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            // 字体：Fraunces（衬线 UI + 编辑性标题，Golden Time 签名字体）
            fontFamily: {
                sans: ['Fraunces', 'ui-serif', 'serif'],
                serif: ['Fraunces', 'ui-serif', 'serif'],
                mono: ['monospace', 'ui-monospace'],
            },
            // 颜色：映射到 Golden Time 语义 token
            colors: {
                background: 'var(--background)',
                foreground: 'var(--foreground)',
                card: 'var(--card)',
                popover: 'var(--popover)',
                muted: 'var(--muted)',
                'muted-foreground': 'var(--muted-foreground)',
                border: 'var(--border)',
                input: 'var(--input)',
                ring: 'var(--ring)',
                primary: {
                    DEFAULT: 'var(--primary)',
                    foreground: 'var(--primary-foreground)',
                },
                secondary: {
                    DEFAULT: 'var(--secondary)',
                    foreground: 'var(--secondary-foreground)',
                },
                accent: {
                    DEFAULT: 'var(--accent)',
                    foreground: 'var(--accent-foreground)',
                },
                destructive: {
                    DEFAULT: 'var(--destructive)',
                    foreground: 'var(--destructive-foreground)',
                },
                success: {
                    DEFAULT: 'var(--success)',
                    foreground: 'var(--success-foreground)',
                },
                warning: {
                    DEFAULT: 'var(--warning)',
                    foreground: 'var(--warning-foreground)',
                },
                brand: {
                    50: 'var(--brand-50)',
                    100: 'var(--brand-100)',
                    200: 'var(--brand-200)',
                    300: 'var(--brand-300)',
                    400: 'var(--brand-400)',
                    500: 'var(--brand-500)',
                    600: 'var(--brand-600)',
                    700: 'var(--brand-700)',
                    800: 'var(--brand-800)',
                    900: 'var(--brand-900)',
                },
                sidebar: {
                    DEFAULT: 'var(--sidebar)',
                    foreground: 'var(--sidebar-foreground)',
                    primary: 'var(--sidebar-primary)',
                    'primary-foreground': 'var(--sidebar-primary-foreground)',
                    accent: 'var(--sidebar-accent)',
                    'accent-foreground': 'var(--sidebar-accent-foreground)',
                    border: 'var(--sidebar-border)',
                    ring: 'var(--sidebar-ring)',
                },
                chart: {
                    1: 'var(--chart-1)',
                    2: 'var(--chart-2)',
                    3: 'var(--chart-3)',
                    4: 'var(--chart-4)',
                    5: 'var(--chart-5)',
                },
            },
            // 圆角：Golden Time 32px 大圆角签名
            borderRadius: {
                DEFAULT: 'var(--radius)',
                vibe: 'var(--radius)',
                'vibe-sm': 'calc(var(--radius) - 8px)',
            },
            // 间距：4.8px 基（Tailwind 默认已含 4px 体系，此处仅显式声明）
            spacing: {
                '4px': '4px',
            },
            boxShadow: {
                // Golden Time 哲学：去阴影，靠色块与边框建立层次，保留命名供兼容
                'vibe': 'var(--shadow)',
                'vibe-sm': 'var(--shadow-sm)',
                'rams': '0 1px 3px rgba(59, 53, 43, 0.05), 0 1px 2px rgba(59, 53, 43, 0.08)',
                'rams-elevated': '0 4px 6px -1px rgba(59, 53, 43, 0.08), 0 2px 4px -2px rgba(59, 53, 43, 0.08)',
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
                    '0%, 100%': { boxShadow: '0 0 0 0 rgba(155, 150, 95, 0.1)' },
                    '50%': { boxShadow: '0 0 20px 5px rgba(155, 150, 95, 0.2)' },
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
