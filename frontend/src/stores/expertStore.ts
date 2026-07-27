/**
 * 财务分析状态管理（专业版）
 *
 * 基于 leofun 项目的专业估值实现
 */

import { create } from 'zustand';
import { analysisApi, valuationApi } from '../services/analysisApi';
import type {
    AnalysisResult,
    AnalysisSummary,
    DCFValuationResult,
    RIValuationResult,
    ValuationComparison,
} from '../services/analysisApi';

interface AnalysisState {
    // 股票代码
    stockCode: string;
    years: number;

    // 加载状态
    loading: boolean;
    error: string | null;

    // 分析结果
    solvency: AnalysisResult | null;
    profitability: AnalysisResult | null;
    growth: AnalysisResult | null;
    operating: AnalysisResult | null;
    summary: AnalysisSummary | null;

    // 估值结果（专业版）
    dcfValuation: DCFValuationResult | null;
    riValuation: RIValuationResult | null;
    valuationComparison: ValuationComparison | null;

    // 操作
    setStockCode: (code: string) => void;
    setYears: (years: number) => void;
    fetchAnalysis: () => Promise<void>;
    fetchValuation: () => Promise<void>;
    reset: () => void;
}

const initialState = {
    stockCode: '',
    years: 5,
    loading: false,
    error: null,
    solvency: null,
    profitability: null,
    growth: null,
    operating: null,
    summary: null,
    dcfValuation: null,
    riValuation: null,
    valuationComparison: null,
};

export const useExpertStore = create<AnalysisState>((set, get) => ({
    ...initialState,

    setStockCode: (code: string) => set({ stockCode: code }),

    setYears: (years: number) => set({ years }),

    fetchAnalysis: async () => {
        const { stockCode, years } = get();
        if (!stockCode) {
            set({ error: '请输入股票代码' });
            return;
        }

        set({ loading: true, error: null });

        try {
            const [solvency, profitability, growth, operating, summary] = await Promise.all([
                analysisApi.getSolvency(stockCode, years),
                analysisApi.getProfitability(stockCode, years),
                analysisApi.getGrowth(stockCode, years),
                analysisApi.getOperating(stockCode, years),
                analysisApi.getSummary(stockCode, years),
            ]);

            set({
                solvency,
                profitability,
                growth,
                operating,
                summary,
                loading: false,
            });
        } catch (err) {
            set({
                error: err instanceof Error ? err.message : '分析请求失败',
                loading: false,
            });
        }
    },

    fetchValuation: async () => {
        const { stockCode } = get();
        if (!stockCode) {
            set({ error: '请输入股票代码' });
            return;
        }

        set({ loading: true, error: null });

        try {
            const [dcfValuation, riValuation, valuationComparison] = await Promise.all([
                valuationApi.getDCF(stockCode),
                valuationApi.getResidualIncome(stockCode),
                valuationApi.getComparison(stockCode),
            ]);

            set({
                dcfValuation,
                riValuation,
                valuationComparison,
                loading: false,
            });
        } catch (err) {
            set({
                error: err instanceof Error ? err.message : '估值请求失败',
                loading: false,
            });
        }
    },

    reset: () => set(initialState),
}));