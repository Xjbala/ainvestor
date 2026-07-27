/**
 * 应用模式状态管理
 *
 * 管理 Dashboard, AI Mode, Expert Mode, Reports 之间的切换。
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * 分析模式类型
 */
export type AnalysisMode = 'dashboard' | 'ai' | 'expert' | 'reports' | 'data' | 'dataView' | 'stocks';

/**
 * 模式状态接口
 */
interface ModeState {
    /** 当前模式 */
    mode: AnalysisMode;

    /** 设置模式 */
    setMode: (mode: AnalysisMode) => void;
}

/**
 * 模式状态 Store
 *
 * 使用 persist 中间件将模式选择持久化到 localStorage
 */
export const useModeStore = create<ModeState>()(
    persist(
        (set) => ({
            mode: 'dashboard', // 默认 Dashboard

            setMode: (mode) => set({ mode }),
        }),
        {
            name: 'ainvestor-mode', // localStorage key
        }
    )
);
