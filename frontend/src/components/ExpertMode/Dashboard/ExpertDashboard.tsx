import { useAnalysisStore } from '../../../stores/analysisStore';
import { ExpertModeLayout } from '../Lab/ExpertModeLayout';
import { companyApi, type Company } from '../../../services/companyApi';
import { useState, useEffect } from 'react';
import { QuotaBadge } from '../../Common/QuotaBadge';

interface ExpertDashboardProps {
    ticker?: string;
}

export function ExpertDashboard({ ticker }: ExpertDashboardProps) {
    const { state, metrics } = useAnalysisStore();
    // 优先使用传入的ticker，否则使用store中的ticker
    const displayTicker = ticker || state.tickers[0];
    const [company, setCompany] = useState<Company | null>(null);

    // 获取公司信息
    useEffect(() => {
        if (displayTicker && displayTicker !== '---') {
            companyApi.getCompany(displayTicker)
                .then(setCompany)
                .catch(err => console.error('[ExpertDashboard] Failed to fetch company:', err));
        }
    }, [displayTicker]);

    return (
        <div>
            <div className="flex justify-end mb-2">
                <QuotaBadge resource="expert_valuation" />
            </div>
            <ExpertModeLayout ticker={displayTicker} metrics={metrics} company={company} />
        </div>
    );
}