// Metric extraction utilities for parsing portfolio_manager recommendations

export interface AnalysisMetrics {
    currentFocus: string;
    valuationGap: number | null;
    targetPrice?: string | null;
    recommendation?: string;
    safetyMargin: string;
    riskLevel: string;
    methodBreakdown?: ValuationMethodBreakdown | null;
    confidence?: string | null;
    divergencePct?: number | null;
}

export interface ValuationMethodRow {
    method: string;
    price: number | null;
    note?: string;
}

export interface ValuationMethodBreakdown {
    blendedPrice: number | null;
    methods: ValuationMethodRow[];
    divergencePct: number | null;
    confidence: string | null;
    headline: string | null;
    risks?: string[];
}

/** 五级评级归一 */
const RATING_ORDER = ['强烈推荐', '推荐', '中性', '谨慎', '回避'] as const;

function normalizeRating(raw: string): string | null {
    if (!raw) return null;
    const t = raw.trim();
    if (/强烈推荐|强烈买入|strong\s*buy/i.test(t)) return '强烈推荐';
    if (/回避|卖出|strong\s*sell|\bsell\b|看跌/i.test(t)) return '回避';
    if (/谨慎|减持|underweight/i.test(t)) return '谨慎';
    if (/中性|持有|观望|hold|neutral/i.test(t)) return '中性';
    if (/推荐|买入|增持|buy|看涨/i.test(t)) return '推荐';
    // 直接命中标准词
    for (const r of RATING_ORDER) {
        if (t.includes(r)) return r;
    }
    return null;
}

export const UNAVAILABLE_TARGET_PRICE = '无法评估';

export function isUnavailableTargetPrice(value: unknown): boolean {
    return typeof value === 'string' && value.trim() === UNAVAILABLE_TARGET_PRICE;
}

export interface InvestmentRecommendation {
    ticker?: string;
    rating?: string;
    target_price?: number | string | null;
    target_price_range?: string | null;
    holding_period?: string | null;
    core_logic?: string;
    risk_warnings?: string;
}

/**
 * 从文本中提取完整的 JSON recommendations 数组。
 */
export function extractInvestmentRecommendations(content: string): InvestmentRecommendation[] | null {
    if (!content) return null;

    const candidates: string[] = [];
    const fence = content.match(/```json\s*(\{[\s\S]*?\})\s*```/i);
    if (fence) candidates.push(fence[1]);

    const bare = content.match(/(\{\s*"recommendations"\s*:\s*\[[\s\S]*?\]\s*\})/);
    if (bare) candidates.push(bare[1]);

    // Python/JS repr 中可能出现单引号
    const barePy = content.match(/(\{\s*['"]recommendations['"]\s*:\s*\[[\s\S]*?\]\s*\})/);
    if (barePy) candidates.push(barePy[1].replace(/'/g, '"'));

    for (const raw of candidates) {
        try {
            const data = JSON.parse(raw);
            const recommendations = data?.recommendations;
            if (
                Array.isArray(recommendations)
                && recommendations.length > 0
                && recommendations.every((item) => item && typeof item === 'object' && !Array.isArray(item))
            ) {
                return recommendations as InvestmentRecommendation[];
            }
        } catch {
            // Try the next candidate.
        }
    }

    return null;
}

/**
 * 从文本中提取第一个 JSON recommendations 对象
 */
export function extractRecommendationJson(content: string): InvestmentRecommendation | null {
    const recommendations = extractInvestmentRecommendations(content);
    if (recommendations) return recommendations[0];

    // 宽松提取 rating / target_price 字段，保持对非标准模型输出的兼容。
    const ratingM = content.match(/"rating"\s*:\s*"([^"]+)"/);
    const tpM = content.match(/"target_price"\s*:\s*(null|"[^"]*"|-?[\d.]+)/);
    const trM = content.match(/"target_price_range"\s*:\s*(null|"[^"]*")/);
    if (ratingM || tpM || trM) {
        const parseVal = (m: RegExpMatchArray | null) => {
            if (!m) return undefined;
            const v = m[1];
            if (v === 'null') return null;
            if (v.startsWith('"')) return v.slice(1, -1);
            const n = Number(v);
            return Number.isFinite(n) ? n : v;
        };
        return {
            rating: ratingM?.[1],
            target_price: parseVal(tpM),
            target_price_range: (parseVal(trM) as string | null) ?? null,
        };
    }
    return null;
}

/**
 * Extract investment rating from portfolio_manager recommendation
 * Looks for: 投资评级: 推荐/中性/回避
 */
export function extractInvestmentRating(content: string): string {
    if (!content) return 'Unknown';

    const fromJson = extractRecommendationJson(content);
    if (fromJson?.rating) {
        return normalizeRating(String(fromJson.rating)) || String(fromJson.rating);
    }

    const ratingMatch = content.match(/(?:投资评级|【投资评级】|综合评级)[：:]\s*([^\n]+)/);
    if (ratingMatch) {
        return normalizeRating(ratingMatch[1]) || ratingMatch[1].trim();
    }

    return 'Unknown';
}

/**
 * Extract valuation gap / upside-downside percentage
 * 注意：不要把「方法分歧」误当作预期收益
 */
export function extractValuationGap(content: string): number | null {
    if (!content) return null;

    const percentagePatterns: Array<{ re: RegExp; sign?: number }> = [
        { re: /潜在上涨\s*[：:]?\s*(\d+(?:\.\d+)?)\s*%/ },
        { re: /上涨空间\s*[：:]?\s*(\d+(?:\.\d+)?)\s*%/ },
        { re: /上行空间\s*[：:]?\s*(\d+(?:\.\d+)?)\s*%/ },
        { re: /upside[_\s-]?(?:downside)?[：:\s]+(-?\d+(?:\.\d+)?)\s*%?/i },
        { re: /潜在下跌\s*[：:]?\s*(\d+(?:\.\d+)?)\s*%/, sign: -1 },
        { re: /下行空间\s*[：:]?\s*(\d+(?:\.\d+)?)\s*%/, sign: -1 },
        { re: /预期收益\s*[：:]?\s*([+-]?\d+(?:\.\d+)?)\s*%/ },
    ];

    for (const { re, sign } of percentagePatterns) {
        const match = content.match(re);
        if (match) {
            const n = parseFloat(match[1]);
            if (!Number.isFinite(n)) continue;
            return sign ? Math.abs(n) * sign : n;
        }
    }

    return null;
}

/**
 * Extract target price from recommendation content
 */
export function extractTargetPrice(content: string): string | null {
    if (!content) return null;

    const fromJson = extractRecommendationJson(content);
    if (fromJson) {
        const tp = fromJson.target_price;
        if (tp != null && tp !== '' && String(tp) !== 'null') {
            const n = Number(tp);
            if (Number.isFinite(n)) return `¥${n.toFixed(2)}`;
            // 文本型目标价
            const s = String(tp).trim();
            if (s && !/无|不适用|null|none/i.test(s)) {
                return s.includes('¥') ? s : `¥${s}`;
            }
        }
        const range = fromJson.target_price_range;
        if (range != null && range !== '' && String(range) !== 'null') {
            const s = String(range).trim();
            if (isUnavailableTargetPrice(s)) return s;
            if (s && !/无有效|无|不适用|null|none/i.test(s)) {
                // 1.0-1.5 / ¥1.0 - ¥1.5
                const rm = s.match(/¥?\s*([\d.]+)\s*[-–~到至]\s*¥?\s*([\d.]+)/);
                if (rm) {
                    return `¥${parseFloat(rm[1]).toFixed(2)} - ¥${parseFloat(rm[2]).toFixed(2)}`;
                }
                return s.includes('¥') ? s : s;
            }
        }
    }

    // Pattern 1: 单点目标价 / 公允价
    const singlePricePatterns = [
        /目标价位[：:]\s*¥?\s*([\d.]+)\s*元?/,
        /目标价[位]?[：:]\s*¥?\s*([\d.]+)\s*元?/,
        /综合公允价[约]?[：:为]?\s*¥?\s*([\d.]+)\s*元?/,
        /公允价[约]?[：:为]?\s*¥?\s*([\d.]+)\s*元?/,
        /合理估值[：:]\s*¥?\s*([\d.]+)\s*元?/,
        /内在价值[：:]\s*¥?\s*([\d.]+)\s*元?/,
        /每股内在价值[为约]?\s*¥?\s*([\d.]+)\s*元?/,
        /blended[_\s]?price[：:\s]+¥?\s*([\d.]+)/i,
    ];

    for (const pattern of singlePricePatterns) {
        const match = content.match(pattern);
        if (match) {
            const n = parseFloat(match[1]);
            // 过滤明显无意义的负价 / 过大噪声（如把“下跌 3623%”里的数字误抓）
            if (Number.isFinite(n) && n > 0 && n < 100000) {
                return `¥${n.toFixed(2)}`;
            }
        }
    }

    // Pattern 2: 目标价位区间
    const rangePatterns = [
        /目标价位区间[：:]\s*¥?\s*([\d.]+)\s*[-–~到至]\s*¥?\s*([\d.]+)/,
        /目标价[位]?区间[：:]\s*¥?\s*([\d.]+)\s*[-–~到至]\s*¥?\s*([\d.]+)/,
        /目标价位[：:]\s*¥?\s*([\d.]+)\s*[-–~到至]\s*¥?\s*([\d.]+)/,
    ];
    for (const re of rangePatterns) {
        const rangeMatch = content.match(re);
        if (rangeMatch) {
            const low = parseFloat(rangeMatch[1]);
            const high = parseFloat(rangeMatch[2]);
            if (Number.isFinite(low) && Number.isFinite(high) && low > 0 && high > 0) {
                return `¥${low.toFixed(2)} - ¥${high.toFixed(2)}`;
            }
        }
    }

    // 决策摘要块中的“无法评估”表示 PM 无法建立目标价。
    if (/目标价位[：:]\s*无法评估/.test(content)) {
        return UNAVAILABLE_TARGET_PRICE;
    }

    // 决策摘要块中的 "—" 表示无目标价
    if (/目标价位[：:]\s*[—–-]/.test(content) || /目标价[位]?[：:]\s*(无|不适用)/.test(content)) {
        return '—';
    }

    return null;
}

/**
 * Extract investment recommendation from content
 * Maps to: 强烈推荐 / 推荐 / 中性 / 谨慎 / 回避
 */
export function extractRecommendation(content: string): string {
    if (!content) return '分析中';

    const fromJson = extractRecommendationJson(content);
    if (fromJson?.rating) {
        return normalizeRating(String(fromJson.rating)) || String(fromJson.rating);
    }

    const ratingPatterns = [
        /投资评级[：:]\s*([^\n]+)/,
        /【投资评级】[：:]\s*([^\n]+)/,
        /投资建议[：:]\s*([^\n]+)/,
        /【投资信号】[：:]\s*([^\n]+)/,
        /综合评级[：:]\s*([^\n]+)/,
        /\*\*投资评级\*\*[：:]\s*([^\n]+)/,
    ];

    for (const pattern of ratingPatterns) {
        const match = content.match(pattern);
        if (match) {
            const normalized = normalizeRating(match[1]);
            if (normalized) return normalized;
        }
    }

    // 全文关键词兜底（优先更强信号）
    if (/强烈推荐|强烈买入/.test(content)) return '强烈推荐';
    if (/建议回避|评级[：:]\s*回避|【投资评级】[：:]\s*回避|"rating"\s*:\s*"回避"/.test(content)) return '回避';
    if (/建议谨慎|评级[：:]\s*谨慎/.test(content)) return '谨慎';
    if (/投资评级[：:]\s*推荐|建议买入/.test(content)) return '推荐';
    if (/投资评级[：:]\s*中性/.test(content)) return '中性';

    return '分析中';
}

/**
 * Extract safety margin from recommendation
 */
export function extractSafetyMargin(content: string): string {
    if (!content) return 'Unknown';

    const lowerContent = content.toLowerCase();

    if (lowerContent.includes('安全边际')) {
        if (
            lowerContent.includes('负') ||
            lowerContent.includes('无安全') ||
            lowerContent.includes('没有安全') ||
            lowerContent.includes('不具备')
        ) {
            return 'Low';
        }
        if (lowerContent.includes('充分') || lowerContent.includes('较高') || lowerContent.includes('高安全')) {
            return 'High';
        }
        if (lowerContent.includes('适度') || lowerContent.includes('中等')) {
            return 'Medium';
        }
        if (lowerContent.includes('有限') || lowerContent.includes('较低')) {
            return 'Low';
        }
    }

    if (lowerContent.includes('极低估值') || lowerContent.includes('严重低估') || lowerContent.includes('深度价值')) {
        return 'High';
    }
    if (lowerContent.includes('低估') || lowerContent.includes('合理估值')) {
        return 'Medium';
    }
    if (lowerContent.includes('高估') || lowerContent.includes('估值偏高') || lowerContent.includes('估值陷阱')) {
        return 'Low';
    }

    if (lowerContent.includes('下行保护') || lowerContent.includes('向下空间有限')) {
        return 'High';
    }

    // 回避/巨亏场景默认低安全边际
    if (/回避|巨亏|资不抵债|退市风险/.test(content)) return 'Low';

    return 'Medium';
}

/**
 * Extract risk level from recommendation
 */
export function extractRiskLevel(content: string): string {
    if (!content) return 'Unknown';

    if (/极高风险|风险等级[：:]\s*极高|高风险/.test(content)) return 'High';
    if (/中等风险|中风险/.test(content)) return 'Medium';
    if (/低风险/.test(content)) return 'Low';

    const lowerContent = content.toLowerCase();
    if (lowerContent.includes('主要风险') || lowerContent.includes('风险提示')) {
        const highRiskKeywords = ['严重', '重大风险', '超预期', '恶化', '暴露', '极高', '退市', '违约'];
        let highRiskCount = 0;
        for (const keyword of highRiskKeywords) {
            const matches = content.match(new RegExp(keyword, 'g'));
            if (matches) highRiskCount += matches.length;
        }
        if (highRiskCount > 2) return 'High';
        if (highRiskCount > 0) return 'Medium';
        return 'Low';
    }

    if (/回避|卖出/.test(content)) return 'High';
    return 'Medium';
}

/**
 * 从估值分析师 / 综合结论文本中解析多方法拆解
 */
export function extractValuationMethodBreakdown(content: string): ValuationMethodBreakdown | null {
    if (!content) return null;

    const blendedMatch =
        content.match(/综合公允价[约]?[：:为]?\s*¥?\s*([\d.]+)/) ||
        content.match(/公允价[约]?[：:为]?\s*¥?\s*([\d.]+)/) ||
        content.match(/blended[_\s]?price[：:\s]+¥?\s*([\d.]+)/i);

    let blendedPrice = blendedMatch ? parseFloat(blendedMatch[1]) : null;
    // 负公允价 / 异常值视为无效
    if (blendedPrice != null && !(blendedPrice > 0 && blendedPrice < 100000)) {
        blendedPrice = null;
    }

    const methods: ValuationMethodRow[] = [];
    const methodPatterns: Array<{ method: string; re: RegExp }> = [
        { method: 'DCF', re: /DCF[^¥\d]{0,20}¥?\s*([\d.]+)/i },
        { method: 'RI', re: /(?:RI|RIM|剩余收益)[^¥\d]{0,20}¥?\s*([\d.]+)/i },
        { method: 'RELATIVE', re: /(?:相对估值|Peer|RELATIVE)[^¥\d]{0,20}¥?\s*([\d.]+)/i },
        { method: 'SOTP', re: /SOTP[^¥\d]{0,20}¥?\s*([\d.]+)/i },
    ];

    for (const { method, re } of methodPatterns) {
        const m = content.match(re);
        if (m) {
            const p = parseFloat(m[1]);
            if (Number.isFinite(p) && p > 0 && p < 100000) {
                methods.push({ method, price: p });
            }
        }
    }

    const tableRowRe = /\|\s*(DCF|RI|RIM|RELATIVE|相对估值|SOTP|剩余收益)\s*\|\s*¥?\s*([\d.]+)/gi;
    let tm: RegExpExecArray | null;
    while ((tm = tableRowRe.exec(content)) !== null) {
        const raw = tm[1].toUpperCase();
        let method = raw;
        if (raw.includes('剩余') || raw === 'RIM') method = 'RI';
        if (raw.includes('相对') || raw === 'PEER') method = 'RELATIVE';
        const p = parseFloat(tm[2]);
        if (!methods.find((x) => x.method === method) && Number.isFinite(p) && p > 0) {
            methods.push({ method, price: p });
        }
    }

    const divMatch =
        content.match(/方法分歧[：:]\s*(\d+(?:\.\d+)?)\s*%/) ||
        content.match(/divergence[_\s]?pct[：:\s]+(\d+(?:\.\d+)?)/i);
    const divergencePct = divMatch ? parseFloat(divMatch[1]) : null;

    const confMatch =
        content.match(/置信度[：:]\s*(高|中|低|high|medium|low)/i) ||
        content.match(/confidence[：:\s]+(high|medium|low)/i);
    let confidence: string | null = null;
    if (confMatch) {
        const c = confMatch[1].toLowerCase();
        if (c === '高' || c === 'high') confidence = 'high';
        else if (c === '中' || c === 'medium') confidence = 'medium';
        else confidence = 'low';
    }

    let headline: string | null = null;
    const headMatch = content.match(/[^\n。]*综合公允价[^\n。]*[。]?/);
    if (headMatch) headline = headMatch[0].trim();

    const risks: string[] = [];
    const riskLineRe = /(?:^|\n)[-*•]\s*((?:风险|注意|警示)[^\n]{4,80})/g;
    let rm: RegExpExecArray | null;
    while ((rm = riskLineRe.exec(content)) !== null && risks.length < 5) {
        risks.push(rm[1].trim());
    }

    if (blendedPrice == null && methods.length === 0) return null;

    return {
        blendedPrice,
        methods,
        divergencePct,
        confidence,
        headline,
        risks,
    };
}

/**
 * 解析置信度文案
 */
export function extractConfidence(content: string): string | null {
    const b = extractValuationMethodBreakdown(content);
    return b?.confidence ?? null;
}

/**
 * 从目标价字符串取中点数值（用于计算预期收益）
 */
export function parseTargetPriceNumber(targetPrice: string | null | undefined): number | null {
    if (!targetPrice || targetPrice === '—' || targetPrice === '计算中...') return null;
    const range = targetPrice.match(/([\d.]+)\s*[-–~]\s*([\d.]+)/);
    if (range) {
        const a = parseFloat(range[1]);
        const b = parseFloat(range[2]);
        if (Number.isFinite(a) && Number.isFinite(b)) return (a + b) / 2;
    }
    const single = targetPrice.replace(/[¥,元\s]/g, '').match(/-?[\d.]+/);
    if (single) {
        const n = parseFloat(single[0]);
        if (Number.isFinite(n) && n > 0) return n;
    }
    return null;
}
