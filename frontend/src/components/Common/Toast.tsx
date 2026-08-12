/**
 * Toast 通知组件
 *
 * 统一替换原生 alert/confirm，提供美观的顶部通知提示。
 * 配色对齐 Golden Time 浅色主题：success/warning/error 用语义浅底，info 用品牌棕。
 */

import React, { createContext, useCallback, useContext, useRef, useState, useMemo } from 'react';
import { X, CheckCircle2, AlertCircle, Info, AlertTriangle } from 'lucide-react';

// ============================================================
// 类型定义
// ============================================================

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastItem {
    id: string;
    type: ToastType;
    message: string;
    duration?: number; // ms, 默认 4000
}

interface ToastContextValue {
    showToast: (type: ToastType, message: string, duration?: number) => void;
    success: (message: string, duration?: number) => void;
    error: (message: string, duration?: number) => void;
    warning: (message: string, duration?: number) => void;
    info: (message: string, duration?: number) => void;
}

// ============================================================
// Context
// ============================================================

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
}

// ============================================================
// Provider
// ============================================================

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);
    const countersRef = useRef(0);

    const removeToast = useCallback((id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const addToast = useCallback((type: ToastType, message: string, duration = 4000) => {
        const id = `toast-${++countersRef.current}-${Date.now()}`;
        const toast: ToastItem = { id, type, message, duration };
        setToasts(prev => [...prev, toast]);

        // 自动消失
        if (duration > 0) {
            setTimeout(() => {
                removeToast(id);
            }, duration);
        }
    }, [removeToast]);

    const value = useMemo<ToastContextValue>(() => ({
        showToast: addToast,
        success: (msg: string, dur?: number) => addToast('success', msg, dur),
        error: (msg: string, dur?: number) => addToast('error', msg, dur),
        warning: (msg: string, dur?: number) => addToast('warning', msg, dur),
        info: (msg: string, dur?: number) => addToast('info', msg, dur),
    }), [addToast]);

    return (
        <ToastContext.Provider value={value}>
            {children}
            <div className="fixed top-4 right-4 z-[100] space-y-2 max-w-sm" aria-live="polite">
                {toasts.map(toast => (
                    <ToastItemComponent
                        key={toast.id}
                        toast={toast}
                        onClose={() => removeToast(toast.id)}
                    />
                ))}
            </div>
        </ToastContext.Provider>
    );
}

// ============================================================
// Toast Item Component
// ============================================================

const ICON_MAP: Record<ToastType, React.ComponentType<{ className?: string }>> = {
    success: CheckCircle2,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
};

// Golden Time 浅色语义底：success 绿 / error 红 / warning 琥珀 / info 品牌棕
// 用 Tailwind 内置浅色调色板，色相对齐 Golden Time，避免 var+alpha 兼容问题
const COLOR_MAP: Record<ToastType, string> = {
    success: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    error: 'bg-red-50 border-red-200 text-red-700',
    warning: 'bg-amber-50 border-amber-200 text-amber-700',
    info: 'bg-stone-50 border-stone-300 text-stone-700',
};

function ToastItemComponent({ toast, onClose }: { toast: ToastItem; onClose: () => void }) {
    const Icon = ICON_MAP[toast.type];
    const colorClass = COLOR_MAP[toast.type];

    return (
        <div
            className={`flex items-start gap-3 border shadow-rams p-4 rounded-vibe animate-slide-in ${colorClass}`}
        >
            <Icon className="w-5 h-5 shrink-0 mt-0.5" />
            <p className="flex-1 text-sm font-medium leading-relaxed text-[var(--foreground)]">{toast.message}</p>
            <button
                onClick={onClose}
                className="shrink-0 p-1 rounded-vibe-sm hover:bg-[var(--accent)] transition-colors text-[var(--muted-foreground)]"
            >
                <X className="w-4 h-4" />
            </button>
        </div>
    );
}
