/**
 * 数据查看主页面组件
 *
 * 包含4个Tab：
 * - 覆盖率：财务矩阵完整度与缺口补采
 * - 财务报表：三大报表原始数据查看（多年对比 + 勾稽校验）
 * - 年报内容：定性报告MD&A结构化字段查看
 * - 新闻舆情：新闻列表+情绪分析查看
 */

import React, { useState } from 'react';
import { Table2, BookOpen, FileText, Newspaper, ShieldCheck } from 'lucide-react';
import { FinancialDataViewer } from '../DataManagement/FinancialDataViewer';
import { FinancialCoveragePanel } from '../DataManagement/FinancialCoveragePanel';
import { QualitativeViewer } from '../DataManagement/QualitativeViewer';
import { NewsViewer } from '../DataManagement/NewsViewer';

type DataTabType = 'coverage' | 'financial' | 'qualitative' | 'news';

export const DataViewer: React.FC = () => {
    const [activeTab, setActiveTab] = useState<DataTabType>('coverage');
    const [focusStockCode, setFocusStockCode] = useState<string>('');

    const TAB_CONFIG: { id: DataTabType; label: string; icon: React.ReactNode }[] = [
        { id: 'coverage', label: '覆盖率', icon: <ShieldCheck className="w-4 h-4" /> },
        { id: 'financial', label: '财务报表', icon: <BookOpen className="w-4 h-4" /> },
        { id: 'qualitative', label: '年报内容', icon: <FileText className="w-4 h-4" /> },
        { id: 'news', label: '新闻舆情', icon: <Newspaper className="w-4 h-4" /> },
    ];

    return (
        <div className="h-full">
            {/* Header */}
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <Table2 className="w-8 h-8 text-indigo-600" />
                    <h1 className="text-2xl font-bold text-gray-900">数据查看</h1>
                </div>
                <p className="text-gray-600">
                    浏览采集数据 — 覆盖率看板、财务报表、年报内容、新闻舆情
                </p>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
                {TAB_CONFIG.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center gap-1.5 px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                            activeTab === tab.id
                                ? 'bg-white text-indigo-600 shadow-sm'
                                : 'text-gray-600 hover:text-gray-900'
                        }`}
                    >
                        {tab.icon}
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            {activeTab === 'coverage' && (
                <FinancialCoveragePanel
                    onSelectCompany={(code) => {
                        setFocusStockCode(code);
                        setActiveTab('financial');
                    }}
                />
            )}
            {activeTab === 'financial' && (
                <FinancialDataViewer initialStockCode={focusStockCode || undefined} />
            )}
            {activeTab === 'qualitative' && <QualitativeViewer />}
            {activeTab === 'news' && <NewsViewer />}
        </div>
    );
};
