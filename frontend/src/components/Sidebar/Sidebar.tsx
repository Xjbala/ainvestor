import React, { useState } from 'react';
import { LayoutDashboard, Zap, Terminal, FileText, Settings, Database, Building2, Table2, Activity, User, Crown, LogOut } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';

export type AppMode = 'dashboard' | 'ai' | 'expert' | 'reports' | 'data' | 'dataView' | 'stocks' | 'account' | 'admin';

interface SidebarProps {
    activeMode: AppMode;
    onSwitchMode: (mode: AppMode) => void;
}

interface NavItem {
    id: AppMode;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    desc: string;
    requireAdmin?: boolean;
}

const NAV_ITEMS: NavItem[] = [
    { id: 'dashboard', icon: LayoutDashboard, label: '工作台', desc: '搜索股票，开始分析' },
    { id: 'ai', icon: Zap, label: 'AI分析', desc: '多智能体协作一键出报告' },
    { id: 'expert', icon: Terminal, label: '专家模式', desc: 'DCF/RIM 估值建模' },
    { id: 'stocks', icon: Building2, label: '股票列表', desc: '浏览 A 股上市公司' },
    { id: 'data', icon: Database, label: '数据采集', desc: '爬虫任务与数据采集' },
    { id: 'dataView', icon: Table2, label: '数据查看', desc: '财务报表、年报、新闻舆情' },
    { id: 'reports', icon: FileText, label: '报告', desc: '历史分析报告库' },
    { id: 'account', icon: User, label: '我的账户', desc: '订阅与配额' },
];

/**
 * 全局侧边导航 —— Golden Time sidebar 规范
 * 暖白底（sidebar token）+ 深棕激活（sidebar-primary）+ 32px 大圆角签名。
 * 保持 64px 折叠图标导航形态，hover 弹出 tooltip 用橄榄金 secondary 底。
 */
export const Sidebar: React.FC<SidebarProps> = ({ activeMode, onSwitchMode }) => {
    const [hoveredId, setHoveredId] = useState<string | null>(null);
    const studioUrl = import.meta.env.VITE_AGENTSCOPE_STUDIO_URL?.trim();
    const { user, isAuthenticated, logout } = useAuthStore();

    const isAdmin = isAuthenticated && user && ['admin', 'superadmin'].includes(user.role);
    const visibleItems = NAV_ITEMS;
    const activeItem = visibleItems.find(n => n.id === activeMode);

    return (
        <nav className="fixed left-0 top-0 h-full w-16 bg-sidebar border-r border-sidebar-border flex flex-col items-center py-6 z-50">
            {/* Logo —— 品牌橙红渐变 */}
            <div className="mb-6">
                <div className="w-10 h-10 bg-gradient-to-br from-brand-500 to-brand-700 rounded-vibe-sm flex items-center justify-center text-primary-foreground font-bold text-lg">
                    V
                </div>
            </div>

            {/* 导航项 */}
            <div className="flex-1 space-y-1.5 w-full px-2">
                {visibleItems.map((item) => {
                    const isActive = activeMode === item.id;
                    const isHovered = hoveredId === item.id;

                    return (
                        <div
                            key={item.id}
                            className="relative"
                            onMouseEnter={() => setHoveredId(item.id)}
                            onMouseLeave={() => setHoveredId(null)}
                        >
                            <button
                                onClick={() => onSwitchMode(item.id)}
                                aria-label={item.label}
                                className={`w-full h-12 rounded-vibe-sm flex items-center justify-center transition-colors
                                    ${isActive
                                        ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                                        : 'text-[var(--muted-foreground)] hover:bg-accent hover:text-[var(--sidebar-foreground)]'
                                    }
                                `}
                            >
                                <item.icon className="w-5 h-5" />
                            </button>

                            {/* Hover tooltip —— 深色 secondary 底 */}
                            {isHovered && (
                                <div className="absolute left-full top-0 ml-2 bg-secondary text-secondary-foreground rounded-vibe-sm px-4 py-3 shadow-rams whitespace-nowrap z-50 animate-fade-in">
                                    <div className="text-sm font-semibold">{item.label}</div>
                                    <div className="text-xs text-white/60 mt-0.5">{item.desc}</div>
                                    <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-secondary" />
                                </div>
                            )}
                        </div>
                    );
                })}

                {studioUrl && (
                    <div
                        className="relative"
                        onMouseEnter={() => setHoveredId('agent-studio')}
                        onMouseLeave={() => setHoveredId(null)}
                    >
                        <a
                            href={studioUrl}
                            aria-label="Agent 追踪"
                            className="w-full h-12 rounded-vibe-sm flex items-center justify-center text-[var(--muted-foreground)] hover:bg-accent hover:text-[var(--sidebar-foreground)] transition-colors"
                        >
                            <Activity className="w-5 h-5" />
                        </a>

                        {hoveredId === 'agent-studio' && (
                            <div className="absolute left-full top-0 ml-2 bg-secondary text-secondary-foreground rounded-vibe-sm px-4 py-3 shadow-rams whitespace-nowrap z-50 animate-fade-in">
                                <div className="text-sm font-semibold">Agent 追踪</div>
                                <div className="text-xs text-white/60 mt-0.5">查看 AgentScope Studio 运行轨迹</div>
                                <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-secondary" />
                            </div>
                        )}
                    </div>
                )}

                {/* Admin 入口（仅 admin/superadmin 可见） */}
                {isAdmin && (
                    <div
                        className="relative"
                        onMouseEnter={() => setHoveredId('admin')}
                        onMouseLeave={() => setHoveredId(null)}
                    >
                        <button
                            onClick={() => onSwitchMode('admin')}
                            aria-label="订阅管理"
                            className={`w-full h-12 rounded-vibe-sm flex items-center justify-center transition-colors
                                ${activeMode === 'admin'
                                    ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                                    : 'text-[var(--muted-foreground)] hover:bg-accent hover:text-[var(--sidebar-foreground)]'
                                }`}
                        >
                            <Crown className="w-5 h-5" />
                        </button>
                        {hoveredId === 'admin' && (
                            <div className="absolute left-full top-0 ml-2 bg-secondary text-secondary-foreground rounded-vibe-sm px-4 py-3 shadow-rams whitespace-nowrap z-50 animate-fade-in">
                                <div className="text-sm font-semibold">订阅管理</div>
                                <div className="text-xs text-white/60 mt-0.5">开通/续期/取消订阅</div>
                                <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-secondary" />
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* 登录态指示（未登录显示登录入口，已登录显示登出） */}
            <div
                className="relative"
                onMouseEnter={() => setHoveredId('auth')}
                onMouseLeave={() => setHoveredId(null)}
            >
                {isAuthenticated ? (
                    <button
                        onClick={() => logout()}
                        aria-label="登出"
                        title={user?.username ? `${user.username} · 登出` : '登出'}
                        className="w-12 h-12 rounded-vibe-sm flex items-center justify-center text-[var(--muted-foreground)] hover:bg-accent hover:text-[var(--sidebar-foreground)] transition-colors mt-auto"
                    >
                        <LogOut className="w-5 h-5" />
                    </button>
                ) : (
                    <button
                        onClick={() => onSwitchMode('account')}
                        aria-label="登录/注册"
                        title="登录 / 注册"
                        className="w-12 h-12 rounded-vibe-sm flex items-center justify-center text-[var(--muted-foreground)] hover:bg-accent hover:text-[var(--sidebar-foreground)] transition-colors mt-auto"
                    >
                        <User className="w-5 h-5" />
                    </button>
                )}
                {hoveredId === 'auth' && (
                    <div className="absolute left-full top-0 ml-2 bg-secondary text-secondary-foreground rounded-vibe-sm px-3 py-2 shadow-rams whitespace-nowrap z-50">
                        <div className="text-sm font-medium">
                            {isAuthenticated ? `${user?.username} · 登出` : '登录 / 注册'}
                        </div>
                        <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-secondary" />
                    </div>
                )}
            </div>

            {/* 设置 */}
            <div
                className="relative"
                onMouseEnter={() => setHoveredId('settings')}
                onMouseLeave={() => setHoveredId(null)}
            >
                <button
                    className="w-12 h-12 rounded-vibe-sm flex items-center justify-center text-[var(--muted-foreground)] hover:bg-accent hover:text-[var(--sidebar-foreground)] transition-colors mt-auto"
                    title="设置（待实现）"
                    aria-label="设置"
                >
                    <Settings className="w-5 h-5" />
                </button>
                {hoveredId === 'settings' && (
                    <div className="absolute left-full top-0 ml-2 bg-secondary text-secondary-foreground rounded-vibe-sm px-3 py-2 shadow-rams whitespace-nowrap z-50">
                        <div className="text-sm font-medium">设置</div>
                        <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-secondary" />
                    </div>
                )}
            </div>

            {/* 当前模式标识 */}
            {activeItem && (
                <div className="mt-2 px-2 py-1 bg-brand-50 rounded-vibe-sm text-center">
                    <div className="text-[10px] text-brand-700 font-medium font-data">{activeItem.label}</div>
                </div>
            )}
        </nav>
    );
};
