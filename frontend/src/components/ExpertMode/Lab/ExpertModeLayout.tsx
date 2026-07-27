import { ExpertSidebar } from './ExpertSidebar';
import { ValuationLab } from './ValuationLab';
import type { Company } from '../../../services/companyApi';
import type { AnalysisMetrics } from '../../../stores/analysisStore';
import './ExpertLab.css';

interface ExpertModeLayoutProps {
    ticker?: string;
    metrics?: AnalysisMetrics;
    company?: Company | null;
}

export function ExpertModeLayout({ ticker, metrics, company }: ExpertModeLayoutProps) {
    return (
        <div className="expert-lab-container">
            <ExpertSidebar ticker={ticker} company={company} />
            <ValuationLab ticker={ticker} metrics={metrics} company={company} />
        </div>
    );
}
