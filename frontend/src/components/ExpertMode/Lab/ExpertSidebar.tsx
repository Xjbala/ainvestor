import { useEffect, useState } from 'react';
import { companyApi, type Company } from '../../../services/companyApi';

interface ExpertSidebarProps {
    ticker?: string;
    company?: Company | null;
}

function formatPrice(price?: number | null): string {
    if (price == null || !Number.isFinite(Number(price))) return '---';
    return `¥${Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function formatMarketCap(mc?: number | null): string {
    if (mc == null || !Number.isFinite(Number(mc)) || Number(mc) <= 0) return '---';
    const n = Number(mc);
    // 库内 market_cap 常见为万元；>1e6 按万元→亿元
    if (n >= 1e6) return `${(n / 1e4).toFixed(2)}亿`;
    if (n >= 100) return `${(n / 100).toFixed(2)}亿`;
    return `${n.toFixed(2)}亿`;
}

export function ExpertSidebar({ ticker = '---', company: companyProp }: ExpertSidebarProps) {
    const [company, setCompany] = useState<Company | null>(companyProp ?? null);

    useEffect(() => {
        if (companyProp) setCompany(companyProp);
    }, [companyProp]);

    useEffect(() => {
        if (!ticker || ticker === '---') {
            setCompany(null);
            return;
        }
        if (companyProp?.stock_code === ticker) {
            return;
        }
        let cancelled = false;
        companyApi
            .getCompany(ticker)
            .then((c) => {
                if (!cancelled) setCompany(c);
            })
            .catch(() => {
                if (!cancelled && !companyProp) setCompany(null);
            });
        return () => {
            cancelled = true;
        };
    }, [ticker, companyProp]);

    const industry = company?.industry_name || '---';

    return (
        <div className="expert-sidebar">
            <div className="stock-card">
                <div className="stock-header-basic">
                    <div className="stock-logo">{ticker?.charAt(0) || '?'}</div>
                    <div className="stock-name-group">
                        <h2>{ticker || '---'}</h2>
                        <p className="stock-company-name">
                            {company?.stock_name || company?.company_name || '---'}
                        </p>
                        <p className="stock-industry">{industry}</p>
                    </div>
                </div>
                <div className="stock-metrics-grid">
                    <div className="metric-item-v">
                        <span className="m-label">当前股价</span>
                        <span className="m-value price">{formatPrice(company?.current_price)}</span>
                    </div>
                    <div className="metric-item-v">
                        <span className="m-label">市值</span>
                        <span className="m-value">{formatMarketCap(company?.market_cap)}</span>
                    </div>
                </div>
            </div>

            <div className="history-section">
                <div className="section-title">
                    <span>历史估值</span>
                    <span className="unit-label">单位: 元</span>
                </div>
                <table className="history-table">
                    <thead>
                        <tr>
                            <th>年份</th>
                            <th>DCF估值</th>
                            <th>RIM估值</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td colSpan={3} style={{ textAlign: 'center', color: '#9ca3af', fontSize: 12 }}>
                                历史快照功能即将接入
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    );
}
