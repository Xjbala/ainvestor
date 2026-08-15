/**
 * 管理员订阅管理页面
 *
 * 功能：
 *  - 列出 plans
 *  - 列出所有订阅记录（最近优先）
 *  - 为用户开通新订阅（选 plan + 周期天数）
 *  - 续期已有订阅（追加天数，可切换 plan）
 *  - 更新订阅状态（active/canceled/expired）
 *
 * 仅 admin/superadmin 可见侧栏入口。
 */

import React, { useEffect, useState } from 'react';
import { Crown, Plus, RefreshCw, RefreshCcw, X } from 'lucide-react';
import { adminApi, type Plan, type Subscription } from '../../services/authApi';
import { useToast } from '../Common/Toast';

const PLAN_LABELS: Record<string, string> = {
    free: '免费版',
    pro: '专业版',
    enterprise: '企业版',
};

const STATUS_OPTIONS = ['active', 'canceled', 'expired', 'past_due'];

export const AdminSubscriptionsPage: React.FC = () => {
    const toast = useToast();
    const [plans, setPlans] = useState<Plan[]>([]);
    const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
    const [loading, setLoading] = useState(false);

    // 开通/续期/改状态三个对话框
    const [createOpen, setCreateOpen] = useState(false);
    const [extendTarget, setExtendTarget] = useState<Subscription | null>(null);
    const [statusTarget, setStatusTarget] = useState<Subscription | null>(null);

    const fetchAll = async () => {
        setLoading(true);
        try {
            const [p, s] = await Promise.all([
                adminApi.listPlans(),
                adminApi.listSubscriptions({ limit: 100 }),
            ]);
            setPlans(p.plans);
            setSubscriptions(s.subscriptions);
        } catch (e: any) {
            toast.error(`加载失败: ${e?.message || e}`);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAll();
    }, []);

    return (
        <div className="max-w-5xl mx-auto">
            <header className="mb-6 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Crown className="w-6 h-6" /> 订阅管理
                    </h1>
                    <p className="text-muted-foreground mt-1">管理员手动开通/续期/取消订阅</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={fetchAll}
                        disabled={loading}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-border rounded-vibe-sm hover:bg-accent disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> 刷新
                    </button>
                    <button
                        onClick={() => setCreateOpen(true)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-sm bg-brand-600 text-primary-foreground rounded-vibe-sm hover:bg-brand-700"
                    >
                        <Plus className="w-4 h-4" /> 开通订阅
                    </button>
                </div>
            </header>

            {/* Plans 概览 */}
            <section className="mb-6">
                <h2 className="text-sm font-medium text-muted-foreground mb-2">订阅计划</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {plans.map((p) => (
                        <div key={p.code} className="bg-card border border-border rounded-vibe p-4">
                            <div className="flex justify-between items-center mb-2">
                                <span className="font-semibold">{p.name}</span>
                                <code className="text-xs bg-muted px-2 py-0.5 rounded">{p.code}</code>
                            </div>
                            <div className="text-xs text-muted-foreground space-y-0.5">
                                <div>AI 分析: <span className="font-data">{p.ai_quota_monthly}/月</span></div>
                                <div>专家估值: <span className="font-data">{p.expert_quota_monthly}/月</span></div>
                                <div>数据 API: <span className="font-data">{p.data_api_quota_monthly}/月</span></div>
                                <div>价格: <span className="font-data">{(p.price_cents / 100).toFixed(2)} 元</span></div>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* 订阅列表 */}
            <section>
                <h2 className="text-sm font-medium text-muted-foreground mb-2">订阅记录</h2>
                {subscriptions.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground bg-card border border-border rounded-vibe">
                        暂无订阅记录
                    </div>
                ) : (
                    <div className="space-y-2">
                        {subscriptions.map((s) => (
                            <div key={s.id} className="bg-card border border-border rounded-vibe p-4 flex items-center justify-between flex-wrap gap-3">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <code className="text-xs bg-muted px-2 py-0.5 rounded truncate">user:{s.user_id}</code>
                                        <span className="text-sm font-medium">{PLAN_LABELS[s.plan_code] || s.plan_code}</span>
                                        <span className={`text-xs px-2 py-0.5 rounded ${
                                            s.status === 'active' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-muted text-muted-foreground'
                                        }`}>{s.status}</span>
                                        {s.cancel_at_period_end && (
                                            <span className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded">
                                                到期取消
                                            </span>
                                        )}
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                        {new Date(s.current_period_start).toLocaleDateString()} ~ {new Date(s.current_period_end).toLocaleDateString()}
                                    </div>
                                    {s.note && <div className="text-xs text-muted-foreground mt-1">备注: {s.note}</div>}
                                </div>
                                <div className="flex gap-1">
                                    <button
                                        onClick={() => setExtendTarget(s)}
                                        className="px-2 py-1 text-xs border border-border rounded hover:bg-accent inline-flex items-center gap-1"
                                    >
                                        <RefreshCcw className="w-3 h-3" /> 续期
                                    </button>
                                    <button
                                        onClick={() => setStatusTarget(s)}
                                        className="px-2 py-1 text-xs border border-border rounded hover:bg-accent"
                                    >
                                        改状态
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            {createOpen && (
                <CreateSubscriptionDialog
                    plans={plans}
                    onClose={() => setCreateOpen(false)}
                    onCreated={() => {
                        setCreateOpen(false);
                        fetchAll();
                    }}
                />
            )}
            {extendTarget && (
                <ExtendSubscriptionDialog
                    subscription={extendTarget}
                    plans={plans}
                    onClose={() => setExtendTarget(null)}
                    onExtended={() => {
                        setExtendTarget(null);
                        fetchAll();
                    }}
                />
            )}
            {statusTarget && (
                <UpdateStatusDialog
                    subscription={statusTarget}
                    onClose={() => setStatusTarget(null)}
                    onUpdated={() => {
                        setStatusTarget(null);
                        fetchAll();
                    }}
                />
            )}
        </div>
    );
};

// ============================================================
// 开通订阅对话框
// ============================================================

const CreateSubscriptionDialog: React.FC<{
    plans: Plan[];
    onClose: () => void;
    onCreated: () => void;
}> = ({ plans, onClose, onCreated }) => {
    const [userId, setUserId] = useState('');
    const [planCode, setPlanCode] = useState(plans[0]?.code || '');
    const [periodDays, setPeriodDays] = useState(30);
    const [note, setNote] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const toast = useToast();

    const submit = async () => {
        if (!userId.trim() || !planCode) {
            toast.warning('请填写用户 ID 并选择计划');
            return;
        }
        setSubmitting(true);
        try {
            await adminApi.createSubscription({
                user_id: userId.trim(),
                plan_code: planCode,
                period_days: periodDays,
                note: note.trim() || undefined,
            });
            toast.success('订阅开通成功');
            onCreated();
        } catch (e: any) {
            toast.error(`开通失败: ${e?.message || e}`);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <DialogShell title="开通订阅" onClose={onClose}>
            <div className="space-y-3">
                <Field label="用户 ID">
                    <input value={userId} onChange={(e) => setUserId(e.target.value)} className="input-base" placeholder="UUID" />
                </Field>
                <Field label="计划">
                    <select value={planCode} onChange={(e) => setPlanCode(e.target.value)} className="input-base">
                        {plans.map((p) => (
                            <option key={p.code} value={p.code}>{p.name} ({p.code})</option>
                        ))}
                    </select>
                </Field>
                <Field label="周期天数">
                    <input type="number" min={1} max={365} value={periodDays} onChange={(e) => setPeriodDays(Number(e.target.value))} className="input-base" />
                </Field>
                <Field label="备注（可选）">
                    <input value={note} onChange={(e) => setNote(e.target.value)} className="input-base" />
                </Field>
                <div className="flex justify-end gap-2 pt-2">
                    <button onClick={onClose} className="px-3 py-1.5 text-sm border border-border rounded-vibe-sm hover:bg-accent">取消</button>
                    <button onClick={submit} disabled={submitting} className="px-3 py-1.5 text-sm bg-brand-600 text-primary-foreground rounded-vibe-sm hover:bg-brand-700 disabled:opacity-50">
                        {submitting ? '开通中...' : '确认开通'}
                    </button>
                </div>
            </div>
        </DialogShell>
    );
};

// ============================================================
// 续期对话框
// ============================================================

const ExtendSubscriptionDialog: React.FC<{
    subscription: Subscription;
    plans: Plan[];
    onClose: () => void;
    onExtended: () => void;
}> = ({ subscription, plans, onClose, onExtended }) => {
    const [periodDays, setPeriodDays] = useState(30);
    const [planCode, setPlanCode] = useState(subscription.plan_code);
    const [note, setNote] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const toast = useToast();

    const submit = async () => {
        setSubmitting(true);
        try {
            await adminApi.extendSubscription(subscription.id, {
                period_days: periodDays,
                plan_code: planCode !== subscription.plan_code ? planCode : undefined,
                note: note.trim() || undefined,
            });
            toast.success('续期成功');
            onExtended();
        } catch (e: any) {
            toast.error(`续期失败: ${e?.message || e}`);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <DialogShell title={`续期订阅 · ${PLAN_LABELS[subscription.plan_code] || subscription.plan_code}`} onClose={onClose}>
            <div className="space-y-3">
                <Field label="切换计划（可选，不变则不传）">
                    <select value={planCode} onChange={(e) => setPlanCode(e.target.value)} className="input-base">
                        {plans.map((p) => (
                            <option key={p.code} value={p.code}>{p.name} ({p.code})</option>
                        ))}
                    </select>
                </Field>
                <Field label="续期天数">
                    <input type="number" min={1} max={365} value={periodDays} onChange={(e) => setPeriodDays(Number(e.target.value))} className="input-base" />
                </Field>
                <Field label="备注（可选）">
                    <input value={note} onChange={(e) => setNote(e.target.value)} className="input-base" />
                </Field>
                <p className="text-xs text-muted-foreground">
                    当前到期时间：{new Date(subscription.current_period_end).toLocaleString('zh-CN')}
                </p>
                <div className="flex justify-end gap-2 pt-2">
                    <button onClick={onClose} className="px-3 py-1.5 text-sm border border-border rounded-vibe-sm hover:bg-accent">取消</button>
                    <button onClick={submit} disabled={submitting} className="px-3 py-1.5 text-sm bg-brand-600 text-primary-foreground rounded-vibe-sm hover:bg-brand-700 disabled:opacity-50">
                        {submitting ? '续期中...' : '确认续期'}
                    </button>
                </div>
            </div>
        </DialogShell>
    );
};

// ============================================================
// 更新状态对话框
// ============================================================

const UpdateStatusDialog: React.FC<{
    subscription: Subscription;
    onClose: () => void;
    onUpdated: () => void;
}> = ({ subscription, onClose, onUpdated }) => {
    const [status, setStatus] = useState(subscription.status);
    const [cancelAtEnd, setCancelAtEnd] = useState(subscription.cancel_at_period_end);
    const [submitting, setSubmitting] = useState(false);
    const toast = useToast();

    const submit = async () => {
        setSubmitting(true);
        try {
            await adminApi.updateSubscriptionStatus(subscription.id, {
                status,
                cancel_at_period_end: cancelAtEnd,
            });
            toast.success('状态已更新');
            onUpdated();
        } catch (e: any) {
            toast.error(`更新失败: ${e?.message || e}`);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <DialogShell title="更新订阅状态" onClose={onClose}>
            <div className="space-y-3">
                <Field label="状态">
                    <select value={status} onChange={(e) => setStatus(e.target.value)} className="input-base">
                        {STATUS_OPTIONS.map((s) => (
                            <option key={s} value={s}>{s}</option>
                        ))}
                    </select>
                </Field>
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={cancelAtEnd} onChange={(e) => setCancelAtEnd(e.target.checked)} />
                    到期后取消（cancel_at_period_end）
                </label>
                <div className="flex justify-end gap-2 pt-2">
                    <button onClick={onClose} className="px-3 py-1.5 text-sm border border-border rounded-vibe-sm hover:bg-accent">取消</button>
                    <button onClick={submit} disabled={submitting} className="px-3 py-1.5 text-sm bg-brand-600 text-primary-foreground rounded-vibe-sm hover:bg-brand-700 disabled:opacity-50">
                        {submitting ? '更新中...' : '确认'}
                    </button>
                </div>
            </div>
        </DialogShell>
    );
};

// ============================================================
// 通用小组件
// ============================================================

const DialogShell: React.FC<{ title: string; onClose: () => void; children: React.ReactNode }> = ({ title, onClose, children }) => (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
        <div className="bg-background border border-border rounded-vibe shadow-rams w-full max-w-md p-6 relative">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">{title}</h3>
                <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
            </div>
            {children}
        </div>
    </div>
);

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
    <div>
        <label className="block text-sm font-medium mb-1">{label}</label>
        {children}
    </div>
);
