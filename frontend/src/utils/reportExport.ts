/**
 * 投资决策报告导出工具
 * 从 DOM 提取已渲染的 Markdown HTML，拼接完整报告文档用于打印/导出 PDF
 */

// Agent 显示信息
interface AgentInfo {
    name: string;
    icon: string;
    status: string;
    summary: string;
}

// 导出所需的数据快照
interface ExportData {
    ticker: string;
    stockName?: string;
    reportHtml: string;
    recommendation?: string;
    targetPrice?: string | number;
    returnRate?: string | number;
    agents: AgentInfo[];
    blendedPrice?: number | null;
    currentPrice?: number | null;
    upsidePct?: number | null;
}

// 评级对应的色彩与标签
function ratingStyle(rec: string): { bg: string; color: string; label: string } {
    const bull = ['强烈推荐', '推荐', '买入', '增持'];
    const bear = ['谨慎', '回避', '卖出', '减持'];
    if (bull.some(r => rec.includes(r))) {
        return { bg: '#13b15a', color: '#fff', label: rec };
    }
    if (bear.some(r => rec.includes(r))) {
        return { bg: '#ef4444', color: '#fff', label: rec };
    }
    return { bg: '#9b965f', color: '#fff', label: rec || '中性' };
}

// 格式化数字
function fmtNum(v: number | null | undefined, prefix = '', suffix = ''): string {
    if (v == null || !Number.isFinite(v)) return '—';
    return `${prefix}${v.toFixed(2)}${suffix}`;
}

function fmtPct(v: number | null | undefined): string {
    if (v == null || !Number.isFinite(v)) return '—';
    const sign = v > 0 ? '+' : '';
    return `${sign}${v.toFixed(1)}%`;
}

/**
 * 生成完整的报告 HTML 文档（用于打印窗口）
 */
export function buildReportHTML(data: ExportData): string {
    const { ticker, stockName, reportHtml, recommendation, targetPrice, returnRate, agents, blendedPrice, currentPrice, upsidePct } = data;

    const rating = ratingStyle(recommendation || '');
    const now = new Date();
    const dateStr = now.toLocaleDateString('zh-CN');
    const timeStr = now.toLocaleTimeString('zh-CN');

    // 关键指标卡片
    const metricsCard = `
        <div class="metrics-card">
            <div class="metric-item">
                <div class="metric-label">投资建议</div>
                <div class="metric-value" style="background:${rating.bg};color:${rating.color}">${rating.label}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">目标价位</div>
                <div class="metric-value">${targetPrice || fmtNum(blendedPrice, '¥')}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">预期收益</div>
                <div class="metric-value ${upsidePct != null && upsidePct < 0 ? 'neg' : 'pos'}">
                    ${returnRate || fmtPct(upsidePct)}
                </div>
            </div>
            <div class="metric-item">
                <div class="metric-label">现价</div>
                <div class="metric-value">${fmtNum(currentPrice, '¥')}</div>
            </div>
        </div>`;

    // Agent 摘要
    const agentsHtml = agents
        .filter(a => a.summary)
        .map(a => `
            <div class="agent-row ${a.status === 'completed' ? 'done' : ''}">
                <span class="agent-icon">${a.icon}</span>
                <div class="agent-detail">
                    <div class="agent-name">${a.name}</div>
                    <div class="agent-summary">${a.summary}</div>
                </div>
            </div>`)
        .join('');

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>投资决策报告 - ${ticker} ${stockName || ''}</title>
<style>
    /* === Golden Time 打印主题 === */
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, "PingFang SC", "Noto Sans SC", "Segoe UI", sans-serif;
        color: #3b352b;
        line-height: 1.7;
        padding: 48px 56px;
        background: #faf8f5;
    }

    /* 报告头 */
    .report-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        border-bottom: 3px solid #8a7a4f;
        padding-bottom: 16px;
        margin-bottom: 28px;
    }
    .report-header h1 {
        font-size: 24px;
        font-weight: 700;
        color: #3b352b;
    }
    .report-header .ticker {
        font-size: 14px;
        color: #8a7a4f;
        font-family: "SF Mono", "JetBrains Mono", monospace;
        margin-top: 4px;
    }
    .report-header .date {
        font-size: 12px;
        color: #978365;
        text-align: right;
    }

    /* 关键指标卡片 */
    .metrics-card {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-bottom: 28px;
    }
    .metric-item {
        background: #fff;
        border: 1px solid #e8e0d0;
        border-radius: 12px;
        padding: 14px 16px;
    }
    .metric-label {
        font-size: 11px;
        color: #978365;
        font-weight: 500;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 18px;
        font-weight: 700;
        color: #3b352b;
        font-family: "SF Mono", "JetBrains Mono", monospace;
        display: inline-block;
        padding: 2px 10px;
        border-radius: 6px;
    }
    .metric-value.pos { color: #13b15a; }
    .metric-value.neg { color: #ef4444; }

    /* Agent 摘要区 */
    .agents-section {
        background: #fff;
        border: 1px solid #e8e0d0;
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 28px;
    }
    .agents-section h2 {
        font-size: 16px;
        font-weight: 600;
        color: #3b352b;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: 1px solid #e8e0d0;
    }
    .agent-row {
        display: flex;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid #f0ebe0;
    }
    .agent-row:last-child { border-bottom: none; }
    .agent-icon { font-size: 16px; flex-shrink: 0; }
    .agent-name { font-size: 13px; font-weight: 600; color: #3b352b; margin-bottom: 2px; }
    .agent-summary { font-size: 12px; color: #6b6555; line-height: 1.5; }

    /* 报告正文（从 DOM 提取的渲染后 Markdown） */
    .report-body {
        background: #fff;
        border: 1px solid #e8e0d0;
        border-radius: 16px;
        padding: 32px 36px;
    }
    .report-body h1 {
        font-size: 20px; font-weight: 700; color: #3b352b;
        margin: 24px 0 12px; padding-bottom: 8px;
        border-bottom: 2px solid #e8e0d0;
    }
    .report-body h2 {
        font-size: 17px; font-weight: 600; color: #3b352b;
        margin: 20px 0 10px; padding-bottom: 6px;
        border-bottom: 1px solid #e8e0d0;
    }
    .report-body h3 { font-size: 15px; font-weight: 600; color: #3b352b; margin: 16px 0 8px; }
    .report-body h4 { font-size: 14px; font-weight: 600; color: #6b6555; margin: 12px 0 6px; }
    .report-body p { margin: 0 0 10px; font-size: 14px; }
    .report-body ul, .report-body ol { padding-left: 22px; margin: 8px 0 12px; }
    .report-body li { margin-bottom: 4px; font-size: 14px; }
    .report-body strong { font-weight: 600; color: #3b352b; }
    .report-body em { font-style: italic; color: #6b6555; }
    .report-body code { background: #f5f0e8; color: #8a6d3b; padding: 2px 6px; border-radius: 4px; font-size: 13px; font-family: monospace; }
    .report-body pre { background: #3b352b; color: #f5f0e8; padding: 14px 16px; border-radius: 10px; overflow-x: auto; margin: 10px 0; font-size: 13px; line-height: 1.6; }
    .report-body pre code { background: none; color: inherit; padding: 0; }
    .report-body blockquote { border-left: 3px solid #8a7a4f; background: #faf5ed; margin: 10px 0; padding: 10px 16px; border-radius: 0 8px 8px 0; font-size: 13px; }
    .report-body table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
    .report-body th { background: #f5f0e8; padding: 10px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #e8e0d0; font-size: 12px; }
    .report-body td { padding: 8px 12px; border-bottom: 1px solid #e8e0d0; color: #6b6555; }
    .report-body hr { border: none; height: 1px; background: linear-gradient(to right, transparent, #e8e0d0, transparent); margin: 16px 0; }

    /* 页脚 */
    .report-footer {
        margin-top: 32px;
        padding-top: 16px;
        border-top: 1px solid #e8e0d0;
        font-size: 11px;
        color: #978365;
        text-align: center;
    }

    /* 打印优化 */
    @media print {
        body { padding: 0; background: #fff; }
        .metrics-card { break-inside: avoid; }
        .agents-section { break-inside: avoid; }
        .report-body h1, .report-body h2 { break-after: avoid; }
        .agent-row { break-inside: avoid; }
    }
    @page { margin: 2cm; }
</style>
</head>
<body>
    <div class="report-header">
        <div>
            <h1>投资决策报告</h1>
            <div class="ticker">${ticker} ${stockName ? '· ' + stockName : ''}</div>
        </div>
        <div class="date">
            生成日期：${dateStr}<br>
            生成时间：${timeStr}
        </div>
    </div>

    ${metricsCard}

    ${agentsHtml ? `<div class="agents-section"><h2>智能体分析摘要</h2>${agentsHtml}</div>` : ''}

    <div class="report-body">
        ${reportHtml || '<p>暂无报告内容</p>'}
    </div>

    <div class="report-footer">
        本报告由 AI Investor 多智能体系统自动生成 · 仅供参考，不构成投资建议 · ${dateStr} ${timeStr}
    </div>
</body>
</html>`;
}

/**
 * 触发打印导出
 * 从隐藏的 DOM 容器中提取已渲染的报告 HTML
 */
export function exportReport(data: ExportData): void {
    const html = buildReportHTML(data);
    const printWindow = window.open('', '_blank', 'width=900,height=700');
    if (!printWindow) {
        alert('无法打开打印窗口，请检查浏览器弹窗拦截设置。');
        return;
    }
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    // 等待样式和内容加载完成后再触发打印
    setTimeout(() => {
        printWindow.focus();
        printWindow.print();
    }, 600);
}
