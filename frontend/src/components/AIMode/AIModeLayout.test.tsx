import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { AIModeLayout } from './AIModeLayout';

describe('AIModeLayout', () => {
    it('does not present an idle session as a report being prepared', () => {
        const markup = renderToStaticMarkup(
            <AIModeLayout ticker="600519" analysisStatus="idle" />,
        );

        expect(markup).toContain('等待启动分析');
        expect(markup).not.toContain('投资决策报告编制中');
    });

    it('replaces a stale progress message after an agent completes', () => {
        const markup = renderToStaticMarkup(
            <AIModeLayout
                ticker="600519"
                analysisStatus="completed"
                agents={[
                    {
                        id: 'fundamentals_analyst',
                        name: '基本面分析师',
                        status: 'complete',
                        content: '正在进行深度分析...',
                        progress: 100,
                        phase: 'analysis',
                        updatedAt: '2026-08-15T01:30:00+00:00',
                    },
                ]}
            />,
        );

        expect(markup).toContain('分析已完成');
        expect(markup).not.toContain('正在进行深度分析...');
    });
});
