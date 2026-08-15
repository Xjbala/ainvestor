import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { formatTimeShort } from '../../utils/timeFormat';
import { AnalystCard } from './AnalystCard';

describe('AnalystCard', () => {
    it('renders the supplied event timestamp', () => {
        const eventTimestamp = '2026-08-15T01:30:00+00:00';
        const markup = renderToStaticMarkup(
            <AnalystCard
                title="基本面分析师"
                icon="📈"
                iconClass="icon-fund"
                status="completed"
                progress={100}
                logs={['分析已完成']}
                timestamp={eventTimestamp}
            />,
        );

        expect(markup).toContain(`[${formatTimeShort(eventTimestamp)}]`);
    });
});
