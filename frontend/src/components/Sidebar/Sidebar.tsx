import React, { useState } from 'react';
import { LayoutDashboard, Zap, Terminal, FileText, Settings, Database, Building2, Table2 } from 'lucide-react';

export type AppMode = 'dashboard' | 'ai' | 'expert' | 'reports' | 'data' | 'dataView' | 'stocks';

interface SidebarProps {
    activeMode: AppMode;
    onSwitchMode: (mode: AppMode) => void;
}

interface NavItem {
    id: AppMode;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    desc: string;
}

const NAV_ITEMS: NavItem[] = [
    { id: 'dashboard', icon: LayoutDashboard, label: '工作台', desc: '搜索股票，开始分析' },
    { id: 'ai', icon: Zap, label: 'AI分析', desc: '多智能体协作一键出报告' },
    { id: 'expert', icon: Terminal, label: '专家模式', desc: 'DCF/RIM 估值建模' },
    { id: 'stocks', icon: Building2, label: '股票列表', desc: '浏览 A 股上市公司' },
    { id: 'data', icon: Database, label: '数据采集', desc: '爬虫任务与数据采集' },
    { id: 'dataView', icon: Table2, label: '数据查看', desc: '财务报表、年报、新闻舆情' },
    { id: 'reports', icon: FileText, label: '报告', desc: '历史分析报告库' },
];

export const Sidebar: React.FC<SidebarProps> = ({ activeMode, onSwitchMode }) => {
    const [hoveredId, setHoveredId] = useState<string | null>(null);

    const activeItem = NAV_ITEMS.find(n => n.id === activeMode);

    return (
        <nav className="fixed left-0 top-0 h-full w-16 bg-white border-r border-gray-200 flex flex-col items-center py-6 z-50 shadow-rams">
            {/* Logo */}
            <div className="mb-6">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg">
                    V
                </div>
            </div>

            {/* Navigation Items */}
            <div className="flex-1 space-y-1 w-full px-2">
                {NAV_ITEMS.map((item) => {
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
                                className={`w-full h-12 rounded-xl flex items-center justify-center transition-all
                                    ${isActive
                                        ? 'bg-blue-50 text-blue-600'
                                        : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'
                                    }
                                `}
                            >
                                <item.icon className="w-5 h-5" />
                            </button>

                            {/* Hover tooltip panel */}
                            {isHovered && (
                                <div className="absolute left-full top-0 ml-2 bg-gray-900 text-white rounded-xl px-4 py-3 shadow-xl whitespace-nowrap z-50 animate-fade-in">
                                    <div className="text-sm font-semibold">{item.label}</div>
                                    <div className="text-xs text-gray-400 mt-0.5">{item.desc}</div>
                                    {/* Arrow */}
                                    <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-gray-900" />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Settings */}
            <div
                className="relative"
                onMouseEnter={() => setHoveredId('settings')}
                onMouseLeave={() => setHoveredId(null)}
            >
                <button
                    className="w-12 h-12 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-50 hover:text-gray-900 transition-colors mt-auto"
                    title="设置（待实现）"
                >
                    <Settings className="w-5 h-5" />
                </button>
                {hoveredId === 'settings' && (
                    <div className="absolute left-full top-0 ml-2 bg-gray-900 text-white rounded-xl px-3 py-2 shadow-xl whitespace-nowrap z-50">
                        <div className="text-sm font-medium">设置</div>
                        <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-gray-900" />
                    </div>
                )}
            </div>

            {/* Active mode label at bottom */}
            {activeItem && (
                <div className="mt-2 px-2 py-1 bg-blue-50 rounded-lg text-center">
                    <div className="text-[10px] text-blue-600 font-medium">{activeItem.label}</div>
                </div>
            )}
        </nav>
    );
};
