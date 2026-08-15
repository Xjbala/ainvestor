import { describe, expect, it } from 'vitest';
import { analysisReducer } from './analysisStore';
import type { AnalysisSession } from '../types/message';

const runningState: AnalysisSession = {
    id: 'session-001',
    tickers: ['600519'],
    date: '2026-08-15',
    status: 'running',
    agents: {
        fundamentals_analyst: {
            id: 'fundamentals_analyst',
            name: '基本面分析师',
            status: 'analyzing',
            content: '正在进行深度分析...',
            progress: 90,
            phase: 'analysis',
        },
    },
    conferenceMessages: [],
    predictions: {},
    report: '',
    currentRound: 0,
    totalRounds: 0,
};

describe('analysisReducer', () => {
    it('finalizes active agents when a session completes', () => {
        const next = analysisReducer(runningState, {
            type: 'SESSION_END',
            payload: { success: true, status: 'completed' },
        });

        expect(next.agents.fundamentals_analyst).toMatchObject({
            status: 'complete',
            progress: 100,
        });
    });
});
