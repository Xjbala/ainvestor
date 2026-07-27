import { useEffect, useState } from 'react';
import { companyApi, type Company } from '../../services/companyApi';

interface StockHeaderProps {
    ticker?: string;
    lastUpdated?: string;
}

interface StockData {
    company: Company | null;
    loading: boolean;
    error: string | null;
}

export function StockHeader({ ticker = '000001', lastUpdated = '--:--:--' }: StockHeaderProps) {
    const [stockData, setStockData] = useState<StockData>({
        company: null,
        loading: false,
        error: null
    });

    useEffect(() => {
        if (!ticker) return;

        const fetchStockData = async () => {
            setStockData({ company: null, loading: true, error: null });
            try {
                const company = await companyApi.getCompany(ticker);
                setStockData({ company, loading: false, error: null });
            } catch (err) {
                console.error('[StockHeader] Failed to fetch company data:', err);
                setStockData({ company: null, loading: false, error: '加载失败' });
            }
        };

        fetchStockData();
    }, [ticker]);

    const { company, loading, error } = stockData;

    return (
        <div className="stock-header">
            <div className="stock-info-left">
                <h1>
                    {ticker}
                    {company?.stock_name && <span className="stock-badge">{company.stock_name}</span>}
                </h1>
                <p className="stock-desc">
                    {loading ? '加载中...' : error || (company?.company_name || '公司信息')}
                    {' · '}
                    最后更新: {lastUpdated}
                </p>
            </div>
            <div className="stock-price-right">
                <p className="current-price">
                    {loading ? '---' : (company?.current_price ? `¥${company.current_price.toFixed(2)}` : '---')}
                </p>
                <p className="price-change">
                    {company?.pe_ratio ? `PE: ${company.pe_ratio.toFixed(2)}` : '---'}
                </p>
            </div>
        </div>
    );
}