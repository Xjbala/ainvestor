/**
 * 数据采集页面组件
 *
 * 爬虫任务管理：创建/监控/日志查看。
 */

import React, { useState } from 'react';
import { Database, Plus, Sparkles } from 'lucide-react';
import { TaskList } from './TaskList';
import { CreateTaskDialog } from './CreateTaskDialog';

type TaskSubTabType = 'stock' | 'financial' | 'batch' | 'qualitative';
type QualitativeSubTabType = 'qualitative' | 'news';

export const DataManagement: React.FC = () => {
    const [taskSubTab, setTaskSubTab] = useState<TaskSubTabType>('financial');
    const [qualitativeSubTab, setQualitativeSubTab] = useState<QualitativeSubTabType>('qualitative');
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [refreshKey, setRefreshKey] = useState(0);

    const handleTaskCreated = () => {
        setRefreshKey(prev => prev + 1);
    };

    // 定性数据子Tab的标题和描述
    const qualitativeInfo = {
        title: qualitativeSubTab === 'qualitative' ? '年报/季报PDF采集' : '新闻舆情采集',
        description: qualitativeSubTab === 'qualitative'
            ? '从巨潮资讯网下载PDF年报，AI解析提取MD&A结构化数据'
            : '采集上市公司相关新闻，进行情绪分析',
    };

    return (
        <div className="h-full">
            {/* Header */}
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <Database className="w-8 h-8 text-primary" />
                    <h1 className="text-2xl font-bold text-foreground">数据采集</h1>
                </div>
                <p className="text-muted-foreground">
                    爬虫任务管理 — 创建采集任务、监控执行进度、查看执行日志
                </p>
            </div>

            {/* Task Sub-Tab Navigation */}
            <div className="flex gap-2 mb-4 bg-muted p-1 rounded-vibe-sm w-fit">
                {(['stock', 'financial', 'batch', 'qualitative'] as TaskSubTabType[]).map((sub) => (
                    <button
                        key={sub}
                        onClick={() => setTaskSubTab(sub)}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                            taskSubTab === sub
                                ? 'bg-card text-primary shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                        }`}
                    >
                        {sub === 'stock' ? '股票数据' :
                         sub === 'financial' ? '财务报表' :
                         sub === 'batch' ? '批量采集' : '定性数据'}
                    </button>
                ))}
            </div>

            {/* Qualitative Sub-Tab */}
            {taskSubTab === 'qualitative' && (
                <div className="flex gap-2 mb-4 bg-muted p-1 rounded-vibe-sm w-fit ml-2">
                    <button
                        onClick={() => setQualitativeSubTab('qualitative')}
                        className={`px-5 py-1.5 rounded-md text-sm font-medium transition-all ${
                            qualitativeSubTab === 'qualitative'
                                ? 'bg-primary text-primary-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                        }`}
                    >
                        年报PDF
                    </button>
                    <button
                        onClick={() => setQualitativeSubTab('news')}
                        className={`px-5 py-1.5 rounded-md text-sm font-medium transition-all ${
                            qualitativeSubTab === 'news'
                                ? 'bg-success text-success-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                        }`}
                    >
                        新闻舆情
                    </button>
                </div>
            )}

            {/* Action Bar */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-lg font-semibold text-foreground">
                        {taskSubTab === 'stock' ? '股票数据同步' :
                         taskSubTab === 'batch' ? '全量批量采集' :
                         taskSubTab === 'qualitative' ? qualitativeInfo.title : '财务报表同步'}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        {taskSubTab === 'stock'
                            ? '同步交易所股票列表和价格数据'
                            : taskSubTab === 'batch'
                            ? '一键采集所有A股上市公司的三大财务报表（支持断点续采）'
                            : taskSubTab === 'qualitative'
                            ? qualitativeInfo.description
                            : '同步公司财务报表数据（资产负债表、利润表、现金流量表）'}
                    </p>
                </div>
                <div className="flex gap-2">
                    {taskSubTab === 'batch' && (
                        <button
                            onClick={() => setIsDialogOpen(true)}
                            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-primary to-brand-700 text-primary-foreground rounded-vibe-sm hover:from-brand-700 hover:to-brand-800 transition-colors font-medium shadow-sm"
                        >
                            <Sparkles className="w-4 h-4" />
                            一键全量采集
                        </button>
                    )}
                    {taskSubTab === 'qualitative' && (
                        <button
                            onClick={() => setIsDialogOpen(true)}
                            className={`flex items-center gap-2 px-4 py-2 text-primary-foreground rounded-vibe-sm hover:opacity-90 transition-colors font-medium shadow-sm ${
                                qualitativeSubTab === 'qualitative'
                                    ? 'bg-gradient-to-r from-brand-600 to-brand-800'
                                    : 'bg-gradient-to-r from-success to-chart-3'
                            }`}
                        >
                            <Sparkles className="w-4 h-4" />
                            {qualitativeSubTab === 'qualitative' ? '采集年报PDF' : '采集新闻舆情'}
                        </button>
                    )}
                    <button
                        onClick={() => setIsDialogOpen(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-vibe-sm hover:bg-brand-700 transition-colors font-medium"
                    >
                        <Plus className="w-5 h-5" />
                        创建任务
                    </button>
                </div>
            </div>

            {/* Task List */}
            <TaskList
                key={`${refreshKey}-${taskSubTab}`}
                activeTab={
                    taskSubTab === 'qualitative'
                        ? qualitativeSubTab
                        : taskSubTab === 'batch'
                        ? 'financial'
                        : taskSubTab
                }
                onRefresh={() => setRefreshKey(prev => prev + 1)}
                showBatchTab={taskSubTab === 'batch'}
            />

            <CreateTaskDialog
                isOpen={isDialogOpen}
                onClose={() => setIsDialogOpen(false)}
                onTaskCreated={handleTaskCreated}
            />
        </div>
    );
};
