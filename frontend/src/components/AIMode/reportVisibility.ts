export type AnalysisStatus = 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';

export function shouldShowReportArea(
    analysisStatus: AnalysisStatus | undefined,
    showReport: boolean,
    report: string | undefined,
): boolean {
    return analysisStatus === 'running' || (showReport && Boolean(report?.trim()));
}
