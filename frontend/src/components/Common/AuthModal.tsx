/**
 * 认证模态框（注册/登录二合一）
 *
 * 注册流程：
 *  1. 填写用户名、邮箱、密码
 *  2. 通过 Turnstile 人机验证
 *  3. 点击「发送验证码」→ 邮箱收到 6 位数字验证码
 *  4. 输入验证码后点击「注册」
 *
 * 登录流程：用户名/邮箱 + 密码
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { X, LogIn, UserPlus } from 'lucide-react';
import Button from './Button';
import { useAuthStore } from '../../stores/authStore';
import { useEntitlementsStore } from '../../stores/entitlementsStore';
import { useToast } from './Toast';
import { authApi } from '../../services/authApi';

interface AuthModalState {
    open: boolean;
    onSuccess?: () => void;
    title?: string;
}

let _setOpen: (s: AuthModalState) => void = () => {};
export const openAuthModal = (opts?: { onSuccess?: () => void; title?: string }) => {
    _setOpen({ open: true, ...opts });
};

declare global {
    interface Window {
        turnstile?: {
            render: (el: HTMLElement, opts: Record<string, unknown>) => string;
            reset: (id: string) => void;
            remove: (id: string) => void;
        };
    }
}

const TURNSTILE_CONTAINER_ID = 'turnstile-container';

export const AuthModal: React.FC = () => {
    const [state, setState] = useState<AuthModalState>({ open: false });
    _setOpen = setState;

    const [mode, setMode] = useState<'login' | 'register'>('login');
    const [username, setUsername] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [code, setCode] = useState('');
    const [turnstileToken, setTurnstileToken] = useState('');
    const [turnstileSiteKey, setTurnstileSiteKey] = useState('');
    const [turnstileEnabled, setTurnstileEnabled] = useState(false);
    const [sendingCode, setSendingCode] = useState(false);
    const [countdown, setCountdown] = useState(0);
    const turnstileWidgetId = useRef<string | null>(null);
    const turnstileContainerRef = useRef<HTMLDivElement | null>(null);

    const { login, register, isLoading, error, clearError } = useAuthStore();
    const refreshEntitlements = useEntitlementsStore((s) => s.refresh);
    const toast = useToast();

    // 加载 Turnstile 配置
    useEffect(() => {
        if (!state.open) return;
        authApi.getTurnstileConfig().then((cfg) => {
            setTurnstileSiteKey(cfg.site_key);
            setTurnstileEnabled(cfg.enabled);
        }).catch(() => {
            setTurnstileEnabled(false);
        });
    }, [state.open]);

    // 渲染 Turnstile widget
    useEffect(() => {
        if (mode !== 'register' || !turnstileEnabled || !turnstileSiteKey || !turnstileContainerRef.current) {
            return;
        }
        if (turnstileWidgetId.current) return;
        if (!window.turnstile) return;

        const id = window.turnstile.render(turnstileContainerRef.current, {
            sitekey: turnstileSiteKey,
            callback: (token: string) => setTurnstileToken(token),
            'expired-callback': () => setTurnstileToken(''),
            'error-callback': () => setTurnstileToken(''),
        });
        turnstileWidgetId.current = id;
    }, [mode, turnstileEnabled, turnstileSiteKey]);

    // 倒计时
    useEffect(() => {
        if (countdown <= 0) return;
        const timer = setInterval(() => {
            setCountdown((c) => Math.max(0, c - 1));
        }, 1000);
        return () => clearInterval(timer);
    }, [countdown]);

    const resetTurnstile = useCallback(() => {
        if (turnstileWidgetId.current && window.turnstile) {
            window.turnstile.reset(turnstileWidgetId.current);
        }
        setTurnstileToken('');
    }, []);

    const close = useCallback(() => {
        setState({ open: false });
        clearError();
        setUsername('');
        setEmail('');
        setPassword('');
        setCode('');
        setTurnstileToken('');
        setCountdown(0);
        if (turnstileWidgetId.current && window.turnstile) {
            window.turnstile.remove(turnstileWidgetId.current);
            turnstileWidgetId.current = null;
        }
    }, [clearError]);

    const handleSendCode = async () => {
        if (!email) {
            toast.error('请先填写邮箱');
            return;
        }
        if (turnstileEnabled && !turnstileToken) {
            toast.error('请先完成人机验证');
            return;
        }
        setSendingCode(true);
        try {
            await authApi.sendCode(email, turnstileToken);
            toast.success('验证码已发送，请查收邮件');
            setCountdown(60);
            resetTurnstile();
        } catch (e: any) {
            toast.error(e?.message || '验证码发送失败');
            resetTurnstile();
        } finally {
            setSendingCode(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (mode === 'login') {
                await login(username, password);
            } else {
                if (turnstileEnabled && !turnstileToken) {
                    toast.error('请先完成人机验证');
                    return;
                }
                if (!code) {
                    toast.error('请输入验证码');
                    return;
                }
                await register(username, email, password, code, turnstileToken);
            }
            await refreshEntitlements();
            toast.success(mode === 'login' ? '登录成功' : '注册成功');
            const cb = state.onSuccess;
            close();
            cb?.();
        } catch (err: any) {
            // 错误已写入 store.error，不需要额外 toast
            resetTurnstile();
        }
    };

    if (!state.open) return null;

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
            <div className="bg-background border border-border rounded-vibe shadow-rams w-full max-w-md p-6 relative animate-fade-in max-h-[90vh] overflow-y-auto">
                <button
                    onClick={close}
                    className="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="关闭"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 rounded-vibe-sm bg-gradient-to-br from-brand-500 to-brand-700 text-primary-foreground flex items-center justify-center">
                        {mode === 'login' ? <LogIn className="w-5 h-5" /> : <UserPlus className="w-5 h-5" />}
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold">{state.title || (mode === 'login' ? '登录' : '注册')}</h2>
                        <p className="text-sm text-muted-foreground">
                            {mode === 'login' ? '登录以解锁更多配额' : '注册账号以继续使用'}
                        </p>
                    </div>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">用户名</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            minLength={3}
                            maxLength={50}
                            className="w-full px-3 py-2 rounded-vibe-sm border border-border bg-input text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                            placeholder="3-50 个字符"
                            autoFocus
                        />
                    </div>

                    {mode === 'register' && (
                        <>
                            <div>
                                <label className="block text-sm font-medium mb-1">邮箱</label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                    className="w-full px-3 py-2 rounded-vibe-sm border border-border bg-input text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="you@example.com"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1">密码</label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    minLength={6}
                                    maxLength={100}
                                    className="w-full px-3 py-2 rounded-vibe-sm border border-border bg-input text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                    placeholder="至少 6 位"
                                />
                            </div>

                            {turnstileEnabled && (
                                <div>
                                    <div ref={turnstileContainerRef} id={TURNSTILE_CONTAINER_ID} className="min-h-[65px]" />
                                </div>
                            )}

                            <div>
                                <label className="block text-sm font-medium mb-1">邮箱验证码</label>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={code}
                                        onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                        required
                                        minLength={6}
                                        maxLength={6}
                                        inputMode="numeric"
                                        className="flex-1 px-3 py-2 rounded-vibe-sm border border-border bg-input text-foreground focus:outline-none focus:ring-2 focus:ring-ring tracking-widest"
                                        placeholder="6 位数字"
                                    />
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={handleSendCode}
                                        isLoading={sendingCode}
                                        disabled={countdown > 0 || sendingCode || (turnstileEnabled && !turnstileToken)}
                                        className="whitespace-nowrap"
                                    >
                                        {countdown > 0 ? `${countdown}s` : '发送验证码'}
                                    </Button>
                                </div>
                            </div>
                        </>
                    )}

                    {mode === 'login' && (
                        <div>
                            <label className="block text-sm font-medium mb-1">密码</label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                minLength={6}
                                maxLength={100}
                                className="w-full px-3 py-2 rounded-vibe-sm border border-border bg-input text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                placeholder="至少 6 位"
                            />
                        </div>
                    )}

                    {error && (
                        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-vibe-sm px-3 py-2">
                            {error}
                        </div>
                    )}

                    <Button type="submit" isLoading={isLoading} className="w-full">
                        {mode === 'login' ? '登录' : '注册'}
                    </Button>
                </form>

                <div className="mt-4 text-center text-sm text-muted-foreground">
                    {mode === 'login' ? '还没有账号？' : '已有账号？'}
                    <button
                        onClick={() => {
                            setMode(mode === 'login' ? 'register' : 'login');
                            clearError();
                            setCode('');
                            setTurnstileToken('');
                            setCountdown(0);
                        }}
                        className="ml-1 text-brand-600 hover:text-brand-700 font-medium"
                    >
                        {mode === 'login' ? '去注册' : '去登录'}
                    </button>
                </div>
            </div>
        </div>
    );
};
