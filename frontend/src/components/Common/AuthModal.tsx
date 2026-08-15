/**
 * 认证模态框（注册/登录二合一）
 *
 * 触发场景：
 *  - 匿名用户触发 402 配额耗尽时弹出（引导注册）
 *  - 侧栏「我的账户」未登录时弹出
 *  - 任何组件调用 AuthModalStore.open()
 *
 * 登录/注册成功后：
 *  - 关闭模态
 *  - 触发 entitlements 刷新
 *  - 调用可选 onSuccess 回调
 */

import React, { useState } from 'react';
import { X, LogIn, UserPlus } from 'lucide-react';
import Button from './Button';
import { useAuthStore } from '../../stores/authStore';
import { useEntitlementsStore } from '../../stores/entitlementsStore';
import { useToast } from './Toast';

interface AuthModalState {
    open: boolean;
    onSuccess?: () => void;
    title?: string;
}

let _setOpen: (s: AuthModalState) => void = () => {};
export const openAuthModal = (opts?: { onSuccess?: () => void; title?: string }) => {
    _setOpen({ open: true, ...opts });
};

export const AuthModal: React.FC = () => {
    const [state, setState] = useState<AuthModalState>({ open: false });
    _setOpen = setState;

    const [mode, setMode] = useState<'login' | 'register'>('login');
    const [username, setUsername] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const { login, register, isLoading, error, clearError } = useAuthStore();
    const refreshEntitlements = useEntitlementsStore((s) => s.refresh);
    const toast = useToast();

    const close = () => {
        setState({ open: false });
        clearError();
        setUsername('');
        setEmail('');
        setPassword('');
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (mode === 'login') {
                await login(username, password);
            } else {
                await register(username, email, password);
            }
            await refreshEntitlements();
            toast.success(mode === 'login' ? '登录成功' : '注册成功');
            const cb = state.onSuccess;
            close();
            cb?.();
        } catch (err: any) {
            // 错误已写入 store.error，不需要额外 toast
        }
    };

    if (!state.open) return null;

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
            <div className="bg-background border border-border rounded-vibe shadow-rams w-full max-w-md p-6 relative animate-fade-in">
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
                    )}

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
