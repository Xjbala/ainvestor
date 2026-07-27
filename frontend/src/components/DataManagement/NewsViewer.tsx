/**
 * 新闻舆情查看页
 *
 * 选择公司 → 查看新闻列表 + 情绪统计。
 */

import React, { useState, useEffect } from 'react';
import { Newspaper, Loader2, AlertCircle, ExternalLink, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { CompanySearchInput } from './CompanySearchInput';
import { crawlerApi, type NewsItem } from '../../services/crawlerApi';

const SENTIMENT_CONFIG: Record<string, { label: string; color: string; bgColor: string; icon: React.ReactNode }> = {
    positive: {
        label: '正面',
        color: 'text-green-700',
        bgColor: 'bg-green-100',
        icon: <TrendingUp className="w-3.5 h-3.5" />,
    },
    negative: {
        label: '负面',
        color: 'text-red-700',
        bgColor: 'bg-red-100',
        icon: <TrendingDown className="w-3.5 h-3.5" />,
    },
    neutral: {
        label: '中性',
        color: 'text-gray-600',
        bgColor: 'bg-gray-100',
        icon: <Minus className="w-3.5 h-3.5" />,
    },
};

export const NewsViewer: React.FC = () => {
    const [stockCode, setStockCode] = useState('');
    const [days, setDays] = useState(90);
    const [news, setNews] = useState<NewsItem[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!stockCode) {
            setNews([]);
            return;
        }
        setIsLoading(true);
        setError('');
        crawlerApi
            .getNewsSentiment(stockCode, days)
            .then(setNews)
            .catch((e) => setError(e.message))
            .finally(() => setIsLoading(false));
    }, [stockCode, days]);

    // 统计
    const stats = news.reduce(
        (acc, n) => {
            acc[n.sentiment_label] = (acc[n.sentiment_label] || 0) + 1;
            acc.totalScore += n.sentiment_score;
            return acc;
        },
        {} as Record<string, number> & { totalScore: number }
    );
    const avgScore = news.length > 0 ? (stats.totalScore || 0) / news.length : 0;

    return (
        <div>
            {/* 控制栏 */}
            <div className="flex flex-wrap items-center gap-4 mb-6">
                <CompanySearchInput value={stockCode} onChange={setStockCode} />
                <select
                    value={days}
                    onChange={(e) => setDays(Number(e.target.value))}
                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                >
                    <option value={30}>近 30 天</option>
                    <option value={90}>近 90 天</option>
                    <option value={180}>近 180 天</option>
                    <option value={365}>近 1 年</option>
                </select>
            </div>

            {/* 加载/错误/空状态 */}
            {isLoading && (
                <div className="flex items-center justify-center py-20 text-gray-500">
                    <Loader2 className="w-6 h-6 animate-spin mr-2" /> 加载中...
                </div>
            )}
            {error && (
                <div className="flex items-center gap-2 py-10 text-red-600">
                    <AlertCircle className="w-5 h-5" /> {error}
                </div>
            )}
            {!isLoading && !error && !stockCode && (
                <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                    <Newspaper className="w-12 h-12 mb-3" />
                    <p>请先选择一家公司查看新闻舆情</p>
                </div>
            )}
            {!isLoading && !error && stockCode && news.length === 0 && (
                <div className="text-center py-10 text-gray-500">暂无新闻数据</div>
            )}

            {/* 情绪统计条 */}
            {news.length > 0 && (
                <div className="flex items-center gap-4 mb-6 p-4 bg-gray-50 rounded-xl">
                    <div className="text-sm text-gray-600">
                        共 <span className="font-bold text-gray-900">{news.length}</span> 条新闻
                    </div>
                    <div className="h-6 w-px bg-gray-300" />
                    {['positive', 'negative', 'neutral'].map((label) => {
                        const cfg = SENTIMENT_CONFIG[label];
                        const count = stats[label] || 0;
                        return (
                            <div key={label} className="flex items-center gap-1.5">
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${cfg.bgColor} ${cfg.color}`}>
                                    {cfg.icon} {cfg.label}
                                </span>
                                <span className="text-sm font-semibold text-gray-800">{count}</span>
                            </div>
                        );
                    })}
                    <div className="h-6 w-px bg-gray-300" />
                    <div className="text-sm text-gray-600">
                        平均情绪分:{' '}
                        <span
                            className={`font-bold ${
                                avgScore > 0.1
                                    ? 'text-green-600'
                                    : avgScore < -0.1
                                    ? 'text-red-600'
                                    : 'text-gray-800'
                            }`}
                        >
                            {avgScore.toFixed(3)}
                        </span>
                    </div>
                </div>
            )}

            {/* 新闻列表 */}
            {news.length > 0 && (
                <div className="space-y-3">
                    {news.map((item) => {
                        const cfg = SENTIMENT_CONFIG[item.sentiment_label] || SENTIMENT_CONFIG.neutral;
                        return (
                            <div
                                key={item.id}
                                className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-sm transition-shadow"
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1 min-w-0">
                                        {/* 标题 */}
                                        {item.url ? (
                                            <a
                                                href={item.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-sm font-medium text-gray-800 hover:text-blue-600 line-clamp-2"
                                            >
                                                {item.title}
                                                <ExternalLink className="w-3 h-3 inline ml-1 opacity-40" />
                                            </a>
                                        ) : (
                                            <p className="text-sm font-medium text-gray-800 line-clamp-2">
                                                {item.title}
                                            </p>
                                        )}
                                        {/* 日期 + 情绪 */}
                                        <div className="flex items-center gap-3 mt-2">
                                            <span className="text-xs text-gray-400">{item.publish_date}</span>
                                            <span
                                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${cfg.bgColor} ${cfg.color}`}
                                            >
                                                {cfg.icon} {cfg.label}
                                            </span>
                                            <span className="text-xs text-gray-500 font-mono">
                                                分数: {item.sentiment_score.toFixed(3)}
                                            </span>
                                        </div>
                                        {/* 关键词 */}
                                        {item.keywords && item.keywords.length > 0 && (
                                            <div className="flex flex-wrap gap-1.5 mt-2">
                                                {item.keywords.slice(0, 8).map((kw, i) => (
                                                    <span
                                                        key={i}
                                                        className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-xs"
                                                    >
                                                        {kw}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
