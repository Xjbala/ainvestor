/**
 * 年报内容查看页
 *
 * 选择公司 → 查看定性报告列表 → 查看报告详情（MD&A 结构化字段）。
 */

import React, { useState, useEffect } from 'react';
import { FileText, Loader2, AlertCircle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { CompanySearchInput } from './CompanySearchInput';
import { crawlerApi, type QualitativeReport } from '../../services/crawlerApi';

const REPORT_TYPE_LABELS: Record<string, string> = {
    annual: '年报',
    semi: '中报',
    q1: '一季报',
    q3: '三季报',
    unknown: '其他',
};

function SectionCard({
    title,
    content,
    icon,
}: {
    title: string;
    content: string | null | undefined;
    icon?: string;
}) {
    if (!content) return null;
    return (
        <div className="bg-card rounded-vibe-sm border border-border p-4">
            <h4 className="font-semibold text-foreground mb-2">
                {icon && <span className="mr-1">{icon}</span>}
                {title}
            </h4>
            <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{content}</p>
        </div>
    );
}

export const QualitativeViewer: React.FC = () => {
    const [stockCode, setStockCode] = useState('');
    const [reports, setReports] = useState<QualitativeReport[]>([]);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [showMarkdown, setShowMarkdown] = useState(false);
    const [markdownContent, setMarkdownContent] = useState<string | null>(null);

    const selectedReport = reports.find((r) => r.id === selectedId) || null;

    useEffect(() => {
        if (!stockCode) {
            setReports([]);
            setSelectedId(null);
            return;
        }
        setIsLoading(true);
        setError('');
        crawlerApi
            .getQualitativeReports(stockCode, false)
            .then((data) => {
                setReports(data);
                // 自动选中第一条报告
                if (data.length > 0) setSelectedId(data[0].id);
            })
            .catch((e) => setError(e.message))
            .finally(() => setIsLoading(false));
    }, [stockCode]);

    // 加载 Markdown
    const loadMarkdown = async () => {
        if (!stockCode || showMarkdown) {
            setShowMarkdown(!showMarkdown);
            return;
        }
        try {
            const all = await crawlerApi.getQualitativeReports(stockCode, true);
            const r = all.find((x) => x.id === selectedId);
            setMarkdownContent(r?.management_discussion || null);
            setShowMarkdown(true);
        } catch {
            /* ignore */
        }
    };

    return (
        <div>
            {/* 控制栏 */}
            <div className="flex items-center gap-4 mb-6">
                <CompanySearchInput value={stockCode} onChange={setStockCode} />
            </div>

            {/* 加载/错误/空状态 */}
            {isLoading && (
                <div className="flex items-center justify-center py-20 text-muted-foreground">
                    <Loader2 className="w-6 h-6 animate-spin mr-2" /> 加载中...
                </div>
            )}
            {error && (
                <div className="flex items-center gap-2 py-10 text-destructive">
                    <AlertCircle className="w-5 h-5" /> {error}
                </div>
            )}
            {!isLoading && !error && !stockCode && (
                <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                    <FileText className="w-12 h-12 mb-3" />
                    <p>请先选择一家公司查看年报内容</p>
                </div>
            )}
            {!isLoading && !error && stockCode && reports.length === 0 && (
                <div className="text-center py-10 text-muted-foreground">暂无定性报告数据</div>
            )}

            {/* 报告列表 + 详情 */}
            {reports.length > 0 && (
                <div className="flex gap-6">
                    {/* 左侧：报告列表 */}
                    <div className="w-64 shrink-0">
                        <h3 className="text-sm font-semibold text-muted-foreground mb-3">报告列表</h3>
                        <div className="space-y-2">
                            {reports.map((r) => (
                                <button
                                    key={r.id}
                                    onClick={() => {
                                        setSelectedId(r.id);
                                        setShowMarkdown(false);
                                        setMarkdownContent(null);
                                    }}
                                    className={`w-full text-left px-3 py-2.5 rounded-vibe-sm border transition-all ${
                                        selectedId === r.id
                                            ? 'border-brand-300 bg-brand-50'
                                            : 'border-border hover:border-input hover:bg-muted'
                                    }`}
                                >
                                    <div className="text-sm font-medium text-foreground">
                                        {REPORT_TYPE_LABELS[r.report_type] || r.report_type}
                                    </div>
                                    <div className="text-xs text-muted-foreground mt-0.5">
                                        {r.report_period}
                                    </div>
                                    {r.publish_date && (
                                        <div className="text-xs text-muted-foreground mt-0.5">
                                            披露: {r.publish_date}
                                        </div>
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 右侧：报告详情 */}
                    <div className="flex-1 min-w-0">
                        {selectedReport ? (
                            <div className="space-y-4">
                                {/* 标题栏 */}
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-bold text-foreground">
                                        {REPORT_TYPE_LABELS[selectedReport.report_type] || selectedReport.report_type}
                                        <span className="ml-2 text-muted-foreground font-normal text-base">
                                            {selectedReport.report_period}
                                        </span>
                                    </h3>
                                    {selectedReport.source_url && (
                                        <a
                                            href={selectedReport.source_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-1 text-sm text-primary hover:text-brand-800"
                                        >
                                            <ExternalLink className="w-4 h-4" /> 原始PDF
                                        </a>
                                    )}
                                </div>

                                {/* 结构化字段 */}
                                <SectionCard title="经营概述" content={selectedReport.overview} icon="📊" />
                                <SectionCard title="收入分析" content={selectedReport.revenue_analysis} icon="💰" />
                                <SectionCard title="核心竞争力" content={selectedReport.core_competencies} icon="🏆" />
                                <SectionCard title="风险因素" content={selectedReport.risk_factors} icon="⚠️" />
                                <SectionCard title="未来展望" content={selectedReport.future_outlook} icon="🔮" />
                                <SectionCard title="研发投入" content={selectedReport.rd_investment} icon="🔬" />
                                <SectionCard title="成本分析" content={selectedReport.cost_analysis} icon="📉" />
                                <SectionCard title="产能规划" content={selectedReport.capacity_plans} icon="🏗️" />

                                {/* 风险关键词 */}
                                {selectedReport.risk_keywords &&
                                    typeof selectedReport.risk_keywords === 'object' &&
                                    Object.keys(selectedReport.risk_keywords).length > 0 && (
                                        <div className="bg-card rounded-vibe-sm border border-border p-4">
                                            <h4 className="font-semibold text-foreground mb-2">⚠️ 风险关键词</h4>
                                            <div className="flex flex-wrap gap-2">
                                                {(Array.isArray(selectedReport.risk_keywords)
                                                    ? selectedReport.risk_keywords
                                                    : Object.keys(selectedReport.risk_keywords)
                                                ).map((kw, i) => (
                                                    <span
                                                        key={i}
                                                        className="px-2 py-1 bg-[rgba(239,68,68,0.06)] text-destructive rounded-md text-xs"
                                                    >
                                                        {typeof kw === 'string' ? kw : String(kw)}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                {/* Markdown 全文折叠 */}
                                {selectedReport.raw_markdown_length != null && (
                                    <div className="border border-border rounded-vibe-sm overflow-hidden">
                                        <button
                                            onClick={loadMarkdown}
                                            className="w-full flex items-center justify-between px-4 py-3 bg-muted hover:bg-muted text-sm text-foreground"
                                        >
                                            <span className="font-medium">
                                                原始Markdown全文
                                                <span className="ml-2 text-xs text-muted-foreground">
                                                    ({selectedReport.raw_markdown_length.toLocaleString()} 字符)
                                                </span>
                                            </span>
                                            {showMarkdown ? (
                                                <ChevronUp className="w-4 h-4" />
                                            ) : (
                                                <ChevronDown className="w-4 h-4" />
                                            )}
                                        </button>
                                        {showMarkdown && (
                                            <pre className="px-4 py-3 text-[11px] leading-relaxed text-[#f2ede7] bg-[#1e1a16] whitespace-pre-wrap break-words max-h-96 overflow-auto">
                                                {markdownContent || '加载中...'}
                                            </pre>
                                        )}
                                    </div>
                                )}

                                {/* 元信息 */}
                                <p className="text-xs text-muted-foreground">
                                    提取方法: {selectedReport.extraction_method || '-'}
                                </p>
                            </div>
                        ) : (
                            <div className="text-center py-10 text-muted-foreground">
                                请从左侧选择一份报告查看详情
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};
