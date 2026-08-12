import { useState, useEffect, useMemo } from 'react';
import { ValuationControls } from './ValuationControls';
import { ValuationHeader } from './ValuationHeader';
import { DCFExplanation } from './DCFExplanation';
import { RIMExplanation } from './RIMExplanation';
import { DCFTabPanel } from './DCFTabPanel';
import { RIMTabPanel } from './RIMTabPanel';
import { RelativeTabPanel } from './RelativeTabPanel';
import { TriangulateTabPanel } from './TriangulateTabPanel';
import { SOTPTabPanel } from './SOTPTabPanel';
import { SkeletonValuationLab } from './SkeletonValuationLab';
import { valuationApi } from '../../../services/analysisApi';
import { companyApi, type Company } from '../../../services/companyApi';
import type { AnalysisMetrics } from '../../../stores/analysisStore';
import './ExpertLab.css';
import './ModelExplanation.css';

type LabTab = 'DCF' | 'RIM' | 'RELATIVE' | 'TRIANGULATE' | 'SOTP';

interface ValuationLabProps {
    ticker?: string;
    metrics?: AnalysisMetrics;
    company?: Company | null;
}

// 后端返回的实际数据类型
interface BackendDCFResult {
    [key: string]: unknown;
    company: Record<string, unknown> | null;
    method: string;
    valuation_date: string;
    base_report_date: string;
    parameters: {
        growth_rate: number;
        terminal_growth_rate: number;
        discount_rate: number;
        tax_rate: number;
        projection_years: number;
        shares_outstanding: number;
        net_debt: number;
    };
    inputs: Record<string, unknown>;
    valuation: {
        pv_projected_fcf: number;
        terminal_value: number;
        pv_terminal_value: number;
        enterprise_value: number;
        equity_value: number;
        intrinsic_value_per_share: number;
        calculation_detail: {
            base_fcf: number;
            projected_fcf: number[];
            pv_projected_fcf_detail: number[];
            terminal_fcf: number;
            terminal_value: number;
            discount_factors: number[];
        };
        scenarios?: {
            conservative: {
                valuation: number;
                upside_downside: number | null;
                rating: string | null;
                fcf_trend: string;
                terminal_assumption: string;
                projected_fcf: number[];
            };
            base: {
                valuation: number;
                upside_downside: number | null;
                rating: string | null;
                fcf_trend: string;
                terminal_assumption: string;
                projected_fcf: number[];
            };
            optimistic: {
                valuation: number;
                upside_downside: number | null;
                rating: string | null;
                fcf_trend: string;
                terminal_assumption: string;
                projected_fcf: number[];
            };
        };
        fcf_trend?: 'decreasing' | 'stable' | 'increasing';
    };
    current_price: number;
    upside_downside: number | null;
    investment_rating: string | null;
    margin_of_safety: {
        margin_percent: number;
        diff: number;
        status: string;
        recommendation: string;
    };
    error?: string;
}

interface BackendRIResult {
    [key: string]: unknown;
    company: Record<string, unknown> | null;
    method: string;
    valuation_date: string;
    base_report_date: string;
    parameters: {
        cost_of_equity: number;
        growth_rate: number;
        terminal_growth_rate: number;
        projection_years: number;
        payout_ratio: number;
        shares_outstanding: number;
    };
    inputs: Record<string, unknown>;
    valuation: {
        base_book_value_per_share: number;
        pv_forecast_ri: number;
        terminal_value_per_share: number;
        pv_terminal_value: number;
        intrinsic_value_per_share: number;
        equity_value: number;
        calculation_detail: {
            current_eps: number;
            current_dps: number;
            current_bps: number;
            current_roe: number;
            dividend_payout_ratio: number;
            projected_eps: number[];
            projected_dps: number[];
            projected_bps: number[];
            projected_roe: number[];
            projected_ri: number[];
            pv_projected_ri_detail: number[];
            terminal_ri: number;
            discount_factors: number[];
        };
        scenarios?: {
            conservative: {
                valuation: number;
                upside_downside: number | null;
                rating: string | null;
                re_trend: string;
                terminal_assumption: string;
            };
            base: {
                valuation: number;
                upside_downside: number | null;
                rating: string | null;
                re_trend: string;
                terminal_assumption: string;
            };
            optimistic: {
                valuation: number;
                upside_downside: number | null;
                rating: string | null;
                re_trend: string;
                terminal_assumption: string;
            };
        };
        re_trend?: 'decreasing' | 'stable' | 'increasing';
    };
    current_price: number;
    upside_downside: number | null;
    investment_rating: string | null;
    margin_of_safety: {
        margin_percent: number;
        diff: number;
        status: string;
        recommendation: string;
    };
    error?: string;
}

export function ValuationLab({ ticker, company: companyProp }: ValuationLabProps) {
    const [currentTab, setCurrentTab] = useState<LabTab>('TRIANGULATE');
    const [scenario, setScenario] = useState<'conservative' | 'base' | 'optimistic'>('base');
    const [wacc, setWacc] = useState(8.5);
    const [g, setG] = useState(3.0);

    // RIM模型参数
    const [costOfEquity, setCostOfEquity] = useState(9.0);
    const [growthRate, setGrowthRate] = useState(15.0);
    const [payoutRatio, setPayoutRatio] = useState(30.0);

    // Data States
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [dcfData, setDcfData] = useState<any>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [rimData, setRimData] = useState<any>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [relativeData, setRelativeData] = useState<any>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [triData, setTriData] = useState<any>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [sotpData, setSotpData] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [dcfError, setDcfError] = useState<string | null>(null);
    const [rimError, setRimError] = useState<string | null>(null);
    const [relativeError, setRelativeError] = useState<string | null>(null);
    const [triError, setTriError] = useState<string | null>(null);
    const [sotpError, setSotpError] = useState<string | null>(null);
    const [extractingSegments, setExtractingSegments] = useState(false);
    const [company, setCompany] = useState<Company | null>(companyProp ?? null);

    // Explanation States
    const [showDCFExplanation, setShowDCFExplanation] = useState(false);
    const [showRIMExplanation, setShowRIMExplanation] = useState(false);

    // 父组件已拉到公司信息时先展示，避免侧栏/页头空窗
    useEffect(() => {
        if (companyProp) setCompany(companyProp);
    }, [companyProp]);

    // Fetch data when ticker changes
    useEffect(() => {
        if (!ticker || ticker === '---') {
            setDcfData(null);
            setRimData(null);
            setRelativeData(null);
            setTriData(null);
            setSotpData(null);
            setDcfError(null);
            setRimError(null);
            setRelativeError(null);
            setTriError(null);
            setSotpError(null);
            setLoading(false);
            return;
        }

        let cancelled = false;

        const fetchData = async () => {
            setLoading(true);
            // 切换股票时清空旧数据，避免展示上一个 ticker 的结果
            setDcfData(null);
            setRimData(null);
            setRelativeData(null);
            setTriData(null);
            setSotpData(null);
            setDcfError(null);
            setRimError(null);
            setRelativeError(null);
            setTriError(null);
            setSotpError(null);

            try {
                const [dcf, rim, relative, tri, sotp, companyInfo] = await Promise.all([
                    valuationApi.getDCF(ticker).catch(e => {
                        console.error('[ValuationLab] DCF API error:', e);
                        return null;
                    }),
                    valuationApi.getResidualIncome(ticker).catch(e => {
                        console.error('[ValuationLab] RI API error:', e);
                        return null;
                    }),
                    valuationApi.getRelative(ticker).catch(e => {
                        console.error('[ValuationLab] Relative API error:', e);
                        return null;
                    }),
                    valuationApi.getTriangulate(ticker).catch(e => {
                        console.error('[ValuationLab] Triangulate API error:', e);
                        return null;
                    }),
                    valuationApi.getSOTP(ticker).catch(e => {
                        console.error('[ValuationLab] SOTP API error:', e);
                        return null;
                    }),
                    companyApi.getCompany(ticker).catch(e => {
                        console.error('[ValuationLab] Company API error:', e);
                        return null;
                    })
                ]);

                if (cancelled) return;

                setDcfData(dcf as unknown as BackendDCFResult);
                setRimData(rim as unknown as BackendRIResult);
                setRelativeData(relative as unknown as BackendDCFResult);
                setTriData(tri as unknown as BackendDCFResult);
                setSotpData(sotp as unknown as BackendDCFResult);
                if (companyInfo) setCompany(companyInfo);

                if (dcf?.error) setDcfError(dcf.error);
                if (rim?.error) setRimError(rim.error);
                if (relative?.error && !relative?.valuation) setRelativeError(relative.error);
                if (tri?.error && !tri?.blended_price) setTriError(tri.error);
                if (sotp) {
                    const sotpObj = sotp as Record<string, unknown>;
                    if (sotpObj.error && !sotpObj.applicable) setSotpError(sotpObj.error as string);
                }

                if (dcf?.parameters) {
                    const dr = dcf.parameters.discount_rate;
                    const tgr = dcf.parameters.terminal_growth_rate;
                    if (typeof dr === 'number' && Number.isFinite(dr)) setWacc(dr * 100);
                    if (typeof tgr === 'number' && Number.isFinite(tgr)) setG(tgr * 100);
                } else if (tri?.wacc?.wacc != null && Number.isFinite(tri.wacc.wacc)) {
                    setWacc(tri.wacc.wacc * 100);
                }

                if (rim?.parameters) {
                    const ce = rim.parameters.cost_of_equity;
                    const gr = rim.parameters.growth_rate;
                    const pr = rim.parameters.payout_ratio;
                    if (typeof ce === 'number' && Number.isFinite(ce)) setCostOfEquity(ce * 100);
                    if (typeof gr === 'number' && Number.isFinite(gr)) setGrowthRate(gr * 100);
                    if (typeof pr === 'number' && Number.isFinite(pr)) setPayoutRatio(pr * 100);
                }

                if (!dcf && !rim && !relative && !tri && !sotp) {
                    setDcfError('无法获取估值数据，请检查股票代码或后端服务');
                }
            } catch (err) {
                if (cancelled) return;
                console.error('[ValuationLab] Valuation API Error:', err);
                const errorMsg = 'Failed to load valuation models: ' + (err as Error).message;
                setDcfError(errorMsg);
                setRimError(errorMsg);
                setTriError(errorMsg);
                setSotpError(errorMsg);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchData();
        return () => {
            cancelled = true;
        };
    }, [ticker]);

    // Get active data based on current tab
    const activeData =
        currentTab === 'DCF' ? dcfData
        : currentTab === 'RIM' ? rimData
        : currentTab === 'RELATIVE' ? relativeData
        : currentTab === 'SOTP' ? sotpData
        : triData;
    const activeError =
        currentTab === 'DCF' ? dcfError
        : currentTab === 'RIM' ? rimError
        : currentTab === 'RELATIVE' ? relativeError
        : currentTab === 'SOTP' ? sotpError
        : triError;

    const handleExtractSegments = async () => {
        if (!ticker || ticker === '---') return;
        setExtractingSegments(true);
        setSotpError(null);
        try {
            const extracted = await valuationApi.extractSegments(ticker);
            const sotp = await valuationApi.getSOTP(ticker);
            const sotpObj = sotp as Record<string, unknown>;
            const extractedObj = extracted as Record<string, unknown>;
            setSotpData(sotp);
            if (sotpObj?.error && !sotpObj?.applicable) {
                const extractedNested = extractedObj?.extracted as Record<string, unknown> | undefined;
                const count =
                    extractedNested?.count ??
                    extractedObj?.saved_count ??
                    (extractedNested?.segments as Array<unknown> | undefined)?.length;
                setSotpError(
                    String(sotpObj.error) + (count != null ? `（抽取到 ${count} 个分部）` : '')
                );
            } else {
                setSotpError(null);
            }
            // 同步刷新综合估值（可能纳入 SOTP）
            const tri = await valuationApi.getTriangulate(ticker).catch(() => null);
            if (tri) {
                setTriData(tri);
                if (tri?.error && !tri?.blended_price) setTriError(tri.error);
                else setTriError(null);
            }
        } catch (err) {
            const msg = (err as Error).message || String(err);
            // 后端 404：未跑定性采集
            if (msg.includes('404') || msg.includes('年报')) {
                setSotpError('分部抽取失败：未找到年报 Markdown，请先在数据管理中跑定性采集任务');
            } else {
                setSotpError('分部抽取失败: ' + msg);
            }
        } finally {
            setExtractingSegments(false);
        }
    };

    // 计算三种情景的估值
    const scenarios = useMemo(() => {
        if (!activeData) return null;

        // 综合估值 bull/base/bear
        if (currentTab === 'TRIANGULATE' && activeData.scenarios) {
            const s = activeData.scenarios;
            const cur = activeData.current_price || 0;
            const ups = (p: number) => (cur ? Math.round((p - cur) / cur * 100) : 0);
            return {
                conservative: {
                    price: Math.round(s.bear?.price || 0),
                    change: ups(s.bear?.price || 0),
                    rating: '---',
                },
                base: {
                    price: Math.round(s.base?.price || activeData.blended_price || 0),
                    change: Math.round(activeData.upside_pct || 0),
                    rating: activeData.investment_rating || '---',
                },
                optimistic: {
                    price: Math.round(s.bull?.price || 0),
                    change: ups(s.bull?.price || 0),
                    rating: '---',
                },
            };
        }

        if (!activeData.valuation) return null;

        // 优先使用后端返回的scenarios数据
        if (activeData.valuation.scenarios) {
            const backendScenarios = activeData.valuation.scenarios;
            const toChange = (v: unknown) => {
                const n = Number(v);
                return Number.isFinite(n) ? n : 0;
            };
            return {
                conservative: {
                    price: Math.round(Number(backendScenarios.conservative?.valuation) || 0),
                    change: toChange(backendScenarios.conservative?.upside_downside),
                    rating: backendScenarios.conservative?.rating || '---'
                },
                base: {
                    price: Math.round(Number(backendScenarios.base?.valuation) || 0),
                    change: toChange(backendScenarios.base?.upside_downside),
                    rating: backendScenarios.base?.rating || '---'
                },
                optimistic: {
                    price: Math.round(Number(backendScenarios.optimistic?.valuation) || 0),
                    change: toChange(backendScenarios.optimistic?.upside_downside),
                    rating: backendScenarios.optimistic?.rating || '---'
                }
            };
        }

        // 如果后端没有返回scenarios，则使用本地计算
        const baseValue = activeData.valuation?.intrinsic_value_per_share ?? 0;
        const currentValue = activeData.current_price ?? 0;
        const baseUpside = activeData.upside_downside ?? 0;

        return {
            conservative: {
                price: Math.round(baseValue * 0.85),
                change: currentValue ? Math.round((baseValue * 0.85 - currentValue) / currentValue * 100) : 0,
                rating: '---'
            },
            base: {
                price: Math.round(baseValue),
                change: Math.round(baseUpside),
                rating: activeData.investment_rating || '---'
            },
            optimistic: {
                price: Math.round(baseValue * 1.15),
                change: currentValue ? Math.round((baseValue * 1.15 - currentValue) / currentValue * 100) : 0,
                rating: '---'
            }
        };
    }, [activeData, currentTab]);

    // Display functions
    const displayPrice = (type: 'conservative' | 'base' | 'optimistic') => {
        if (!scenarios) return '---';
        return `¥${scenarios[type].price.toLocaleString()}`;
    };

    const displayChange = (type: 'conservative' | 'base' | 'optimistic') => {
        if (!scenarios) return '---';
        const change = Number(scenarios[type].change);
        if (!Number.isFinite(change)) return '---';
        return `${change > 0 ? '+' : ''}${change}%`;
    };

    const isGrowthPositive = (type: 'conservative' | 'base' | 'optimistic') => {
        return (scenarios?.[type]?.change ?? 0) > 0;
    };

    // 生成DCF图表数据
    const generateDCFChartData = () => {
        if (!dcfData || !dcfData.valuation?.calculation_detail) return [];
        const detail = dcfData.valuation.calculation_detail;
        return detail.projected_fcf.map((fcf: number, index: number) => ({
            year: 2025 + index,
            fcf: fcf,
            pv_fcf: detail.pv_projected_fcf_detail?.[index] || 0
        }));
    };

    // 生成RIM图表数据
    const generateRIMChartData = () => {
        if (!rimData || !rimData.valuation?.calculation_detail) return [];
        const detail = rimData.valuation.calculation_detail;
        return detail.projected_ri.map((ri: number, index: number) => ({
            year: 2025 + index,
            ri: ri,
            pv_ri: detail.pv_projected_ri_detail?.[index] || 0
        }));
    };

    const handleRecalculate = async () => {
        if (!ticker || ticker === '---') return;

        setLoading(true);
        setDcfError(null);
        setRimError(null);
        setRelativeError(null);
        setTriError(null);
        setSotpError(null);

        try {
            if (currentTab === 'DCF') {
                const dcfResult = await valuationApi.getDCF(ticker, {
                    discount_rate: wacc / 100,
                    terminal_growth_rate: g / 100
                });
                setDcfData(dcfResult as unknown as BackendDCFResult);
                if (dcfResult?.error) setDcfError(dcfResult.error);
            } else if (currentTab === 'RIM') {
                const rimResult = await valuationApi.getResidualIncome(ticker, {
                    cost_of_equity: costOfEquity / 100,
                    growth_rate: growthRate / 100,
                    payout_ratio: payoutRatio / 100
                });
                setRimData(rimResult as unknown as BackendRIResult);
                if (rimResult?.error) setRimError(rimResult.error);
            } else if (currentTab === 'RELATIVE') {
                const rel = await valuationApi.getRelative(ticker);
                setRelativeData(rel as unknown as BackendDCFResult);
                if (rel?.error && !rel?.valuation) setRelativeError(rel.error);
            } else if (currentTab === 'SOTP') {
                const sotp = await valuationApi.getSOTP(ticker);
                setSotpData(sotp);
                if ((sotp as Record<string, unknown>)?.error && !(sotp as Record<string, unknown>)?.applicable) setSotpError((sotp as Record<string, unknown>).error as string);
                else setSotpError(null);
            } else {
                const tri = await valuationApi.getTriangulate(ticker);
                setTriData(tri as unknown as BackendDCFResult);
                if (tri?.error && !tri?.blended_price) setTriError(tri.error);
                // 同步刷新分项
                const [dcf, rim, rel, sotp] = await Promise.all([
                    valuationApi.getDCF(ticker).catch(() => null),
                    valuationApi.getResidualIncome(ticker).catch(() => null),
                    valuationApi.getRelative(ticker).catch(() => null),
                    valuationApi.getSOTP(ticker).catch(() => null),
                ]);
                if (dcf) {
                    setDcfData(dcf as unknown as BackendDCFResult);
                    if (dcf.error) setDcfError(dcf.error);
                }
                if (rim) {
                    setRimData(rim as unknown as BackendRIResult);
                    if (rim.error) setRimError(rim.error);
                }
                if (rel) {
                    setRelativeData(rel as unknown as BackendDCFResult);
                    if (rel.error && !rel.valuation) setRelativeError(rel.error);
                }
                if (sotp) {
                    setSotpData(sotp);
                    const sotpObj = sotp as Record<string, unknown>;
                    if (sotpObj.error && !sotpObj.applicable) setSotpError(sotpObj.error as string);
                }
            }
        } catch (err) {
            console.error('[ValuationLab] Recalculate error:', err);
            const errorMsg = '重新计算失败: ' + (err as Error).message;
            if (currentTab === 'DCF') setDcfError(errorMsg);
            else if (currentTab === 'RIM') setRimError(errorMsg);
            else if (currentTab === 'RELATIVE') setRelativeError(errorMsg);
            else if (currentTab === 'SOTP') setSotpError(errorMsg);
            else setTriError(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    const headerPrice =
        company?.current_price ??
        activeData?.current_price ??
        dcfData?.current_price ??
        triData?.current_price;

    return (
        <div className="expert-main">
            <ValuationHeader
                ticker={ticker}
                name={company?.stock_name || company?.company_name}
                onRecalculate={handleRecalculate}
                currentPrice={headerPrice != null ? Number(headerPrice) : undefined}
                marketCap={company?.market_cap != null ? Number(company.market_cap) : undefined}
                recalculating={loading}
            />

            <div className="lab-content">
                <div className="lab-tabs">
                    <div
                        className={`lab-tab ${currentTab === 'TRIANGULATE' ? 'active' : ''}`}
                        onClick={() => setCurrentTab('TRIANGULATE')}
                    >
                        综合估值
                    </div>
                    <div
                        className={`lab-tab ${currentTab === 'DCF' ? 'active' : ''}`}
                        onClick={() => setCurrentTab('DCF')}
                    >
                        DCF现金流折现
                        <span
                            className="info-icon"
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowDCFExplanation(true);
                            }}
                            title="点击查看DCF模型说明"
                        >
                            i
                        </span>
                    </div>
                    <div
                        className={`lab-tab ${currentTab === 'RIM' ? 'active' : ''}`}
                        onClick={() => setCurrentTab('RIM')}
                    >
                        剩余收益 (RIM)
                        <span
                            className="info-icon"
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowRIMExplanation(true);
                            }}
                            title="点击查看RIM模型说明"
                        >
                            i
                        </span>
                    </div>
                    <div
                        className={`lab-tab ${currentTab === 'RELATIVE' ? 'active' : ''}`}
                        onClick={() => setCurrentTab('RELATIVE')}
                    >
                        相对估值
                    </div>
                    <div
                        className={`lab-tab ${currentTab === 'SOTP' ? 'active' : ''}`}
                        onClick={() => setCurrentTab('SOTP')}
                    >
                        SOTP 分部
                    </div>
                </div>

                <div className="flex justify-between items-center mb-4">
                    {loading && <span className="text-sm text-brand-600 flex items-center gap-2"><span className="inline-block w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></span>正在计算估值模型...</span>}
                    {activeError && (
                        <span className="text-sm text-destructive">
                            {currentTab === 'DCF' ? 'DCF: '
                                : currentTab === 'RIM' ? 'RIM: '
                                : currentTab === 'RELATIVE' ? '相对估值: '
                                : currentTab === 'SOTP' ? 'SOTP: '
                                : '综合: '}
                            {activeError}
                        </span>
                    )}
                    {!loading && !activeError && activeData && (() => {
                        const data = activeData as Record<string, unknown>;
                        const valuation = data.valuation as Record<string, unknown> | undefined;
                        return (
                        <span className="text-sm text-muted-foreground">
                            当前股价:{' '}
                            {(() => {
                                const p = data.current_price ?? company?.current_price;
                                return p != null && Number.isFinite(Number(p))
                                    ? `¥${Number(p).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                                    : '---';
                            })()}{' '}
                            | 投资评级: {data.investment_rating as string || '---'}
                            {currentTab === 'TRIANGULATE' && data.blended_price != null && (
                                <> | 综合公允价: ¥{Number(data.blended_price).toFixed(2)}</>
                            )}
                            {currentTab === 'SOTP' && valuation?.intrinsic_value_per_share != null && (
                                <> | SOTP: ¥{Number(valuation.intrinsic_value_per_share).toFixed(2)}</>
                            )}
                        </span>
                        );
                    })()}
                </div>

                <ValuationControls
                    wacc={wacc}
                    onWaccChange={setWacc}
                    g={g}
                    onGChange={setG}
                    currentScenario={scenario}
                    onScenarioChange={setScenario}
                    currentTab={currentTab}
                    costOfEquity={costOfEquity}
                    onCostOfEquityChange={setCostOfEquity}
                    growthRate={growthRate}
                    onGrowthRateChange={setGrowthRate}
                    payoutRatio={payoutRatio}
                    onPayoutRatioChange={setPayoutRatio}
                />

                {/* Tab 内容区域 */}
                {loading ? (
                    <SkeletonValuationLab />
                ) : currentTab === 'TRIANGULATE' ? (
                    !activeError || triData?.blended_price ? (
                        <TriangulateTabPanel data={triData} loading={loading} />
                    ) : (
                        <div className="text-center py-12 text-muted-foreground">
                            <p className="text-lg mb-2">无法显示综合估值</p>
                            <p className="text-sm">{activeError}</p>
                        </div>
                    )
                ) : currentTab === 'RELATIVE' ? (
                    !activeError || relativeData?.valuation ? (
                        <RelativeTabPanel
                            data={relativeData}
                            loading={loading}
                            scenario={scenario}
                            displayPrice={displayPrice}
                            displayChange={displayChange}
                            isGrowthPositive={isGrowthPositive}
                        />
                    ) : (
                        <div className="text-center py-12 text-muted-foreground">
                            <p className="text-lg mb-2">相对估值不可用</p>
                            <p className="text-sm">{activeError}</p>
                        </div>
                    )
                ) : currentTab === 'SOTP' ? (
                    <SOTPTabPanel
                        data={sotpData}
                        loading={loading || extractingSegments}
                        onExtract={handleExtractSegments}
                        extracting={extractingSegments}
                    />
                ) : !activeError && activeData?.valuation ? (
                    currentTab === 'DCF' ? (
                        <DCFTabPanel
                            data={dcfData}
                            loading={loading}
                            scenario={scenario}
                            wacc={wacc}
                            g={g}
                            generateChartData={generateDCFChartData}
                            displayPrice={displayPrice}
                            displayChange={displayChange}
                            isGrowthPositive={isGrowthPositive}
                        />
                    ) : (
                        <RIMTabPanel
                            data={rimData}
                            loading={loading}
                            scenario={scenario}
                            wacc={wacc}
                            g={g}
                            generateChartData={generateRIMChartData}
                            displayPrice={displayPrice}
                            displayChange={displayChange}
                            isGrowthPositive={isGrowthPositive}
                        />
                    )
                ) : !loading && activeError ? (
                    <div className="text-center py-12 text-muted-foreground">
                        <p className="text-lg mb-2">无法显示估值模型</p>
                        <p className="text-sm">{currentTab === 'DCF' ? 'DCF模型' : 'RIM模型'}暂时无法使用</p>
                    </div>
                ) : !loading && !activeError && !activeData?.valuation ? (
                    <div className="text-center py-12 text-muted-foreground">
                        <p className="text-lg mb-2">暂无估值数据</p>
                        <p className="text-sm">请在上方输入股票代码后重试</p>
                    </div>
                ) : null}
            </div>

            {/* 说明页面 */}
            {showDCFExplanation && (
                <DCFExplanation onClose={() => setShowDCFExplanation(false)} />
            )}
            {showRIMExplanation && (
                <RIMExplanation onClose={() => setShowRIMExplanation(false)} />
            )}
        </div>
    );
}