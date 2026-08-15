import { describe, expect, it } from 'vitest';
import { shouldShowReportArea } from './reportVisibility';

describe('shouldShowReportArea', () => {
    it('shows the report area only while running or explicitly opened with a report', () => {
        expect(shouldShowReportArea('running', false, '')).toBe(true);
        expect(shouldShowReportArea('completed', false, '完整报告')).toBe(false);
        expect(shouldShowReportArea('completed', true, '完整报告')).toBe(true);
    });
});
