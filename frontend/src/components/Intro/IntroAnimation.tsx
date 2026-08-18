/**
 * 系统介绍动画页（增强版）
 *
 * 视觉层次：
 *  1. Canvas 粒子网络背景（始终运行，鼠标交互）
 *  2. SVG 场景可视化（每场景不同的动态图表）
 *  3. 文字动画（打字机 + 渐变 shimmer）
 *  4. 场景间过渡（缩放 + 淡出）
 *
 * 色彩：Golden Time 暖白金棕主题
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { ArrowRight, Database, Brain, BarChart3, Shield, TrendingUp } from 'lucide-react';

const INTRO_SEEN_KEY = 'ainvestor.introSeen';
const SCENE_DURATION = 3200;

type SceneId = 'title' | 'data' | 'agents' | 'valuation' | 'risk';

interface Scene {
    id: SceneId;
    title: string;
    subtitle: string;
    icon: React.ReactNode;
}

const SCENES: Scene[] = [
    {
        id: 'title',
        title: 'AI Investor',
        subtitle: '多智能体价值投资分析系统',
        icon: <TrendingUp className="w-10 h-10" strokeWidth={1.5} />,
    },
    {
        id: 'data',
        title: '数据为基',
        subtitle: '结构化财务数据是可验证的资产，Agent 在其上推理而非臆造',
        icon: <Database className="w-10 h-10" strokeWidth={1.5} />,
    },
    {
        id: 'agents',
        title: '多智能体协作',
        subtitle: '基本面 × 估值 × 风险 × 投资组合经理，会议讨论达成共识',
        icon: <Brain className="w-10 h-10" strokeWidth={1.5} />,
    },
    {
        id: 'valuation',
        title: '六维估值',
        subtitle: 'DCF · 剩余收益 · 相对估值 · SOTP · WACC · 三角融合',
        icon: <BarChart3 className="w-10 h-10" strokeWidth={1.5} />,
    },
    {
        id: 'risk',
        title: '风险锚定',
        subtitle: '四维财务分析 + 风险评估，每一份评级都有数据支撑',
        icon: <Shield className="w-10 h-10" strokeWidth={1.5} />,
    },
];

// ============================================================
// 场景可视化：自绘折线图
// ============================================================

const LineChartViz: React.FC = () => {
    const points = [
        [0, 80],
        [20, 65],
        [40, 70],
        [60, 45],
        [80, 50],
        [100, 25],
    ];
    const pathD = points
        .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`)
        .join(' ');
    const areaD = `${pathD} L 100 100 L 0 100 Z`;

    return (
        <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="none">
            <defs>
                <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--brand-500)" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="var(--brand-500)" stopOpacity="0" />
                </linearGradient>
            </defs>
            <path
                d={areaD}
                fill="url(#lineGrad)"
                style={{
                    animation: 'intro-area-in 1.2s ease-out 0.3s both',
                }}
            />
            <path
                d={pathD}
                fill="none"
                stroke="var(--brand-600)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{
                    strokeDasharray: 300,
                    strokeDashoffset: 300,
                    animation: 'intro-draw-line 2s ease-out 0.2s forwards',
                }}
            />
            {points.map((p, i) => (
                <circle
                    key={i}
                    cx={p[0]}
                    cy={p[1]}
                    r="1.5"
                    fill="var(--brand-600)"
                    style={{
                        opacity: 0,
                        animation: `intro-dot-in 0.3s ease-out ${0.4 + i * 0.3}s forwards`,
                    }}
                />
            ))}
        </svg>
    );
};

// ============================================================
// 场景可视化：柱状图
// ============================================================

const BarChartViz: React.FC = () => {
    const bars = [40, 65, 50, 80, 60, 90];
    return (
        <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="none">
            {bars.map((h, i) => (
                <rect
                    key={i}
                    x={8 + i * 15}
                    y={100 - h}
                    width="10"
                    height={h}
                    rx="1"
                    fill={i % 2 === 0 ? 'var(--brand-500)' : 'var(--brand-600)'}
                    style={{
                        transformOrigin: `${13 + i * 15}px 100px`,
                        transform: 'scaleY(0)',
                        animation: `intro-bar-grow 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) ${i * 0.12}s forwards`,
                    }}
                />
            ))}
        </svg>
    );
};

// ============================================================
// 场景可视化：多智能体网络图
// ============================================================

const AgentNetworkViz: React.FC = () => {
    const nodes = [
        { x: 50, y: 20, label: '基本面', color: 'var(--brand-600)' },
        { x: 80, y: 50, label: '估值', color: 'var(--brand-500)' },
        { x: 50, y: 80, label: '风险', color: 'var(--brand-600)' },
        { x: 20, y: 50, label: 'PM', color: 'var(--brand-500)' },
    ];
    const center = { x: 50, y: 50 };

    return (
        <svg viewBox="0 0 100 100" className="w-full h-full">
            {/* 中心节点到各节点的连线 */}
            {nodes.map((n, i) => (
                <line
                    key={`line-${i}`}
                    x1={center.x}
                    y1={center.y}
                    x2={n.x}
                    y2={n.y}
                    stroke="var(--brand-400)"
                    strokeWidth="0.8"
                    strokeDasharray="2 2"
                    style={{
                        opacity: 0,
                        animation: `intro-fade-in 0.5s ease-out ${0.3 + i * 0.15}s forwards`,
                    }}
                />
            ))}
            {/* 节点间连线（环形） */}
            {nodes.map((n, i) => {
                const next = nodes[(i + 1) % nodes.length];
                return (
                    <line
                        key={`ring-${i}`}
                        x1={n.x}
                        y1={n.y}
                        x2={next.x}
                        y2={next.y}
                        stroke="var(--brand-300)"
                        strokeWidth="0.5"
                        style={{
                            opacity: 0,
                            animation: `intro-fade-in 0.5s ease-out ${0.6 + i * 0.1}s forwards`,
                        }}
                    />
                );
            })}
            {/* 中心节点 */}
            <circle
                cx={center.x}
                cy={center.y}
                r="4"
                fill="var(--brand-600)"
                style={{
                    transformOrigin: '50px 50px',
                    animation: 'intro-pulse 2s ease-in-out infinite',
                }}
            />
            <circle
                cx={center.x}
                cy={center.y}
                r="4"
                fill="none"
                stroke="var(--brand-600)"
                strokeWidth="0.5"
                style={{
                    transformOrigin: '50px 50px',
                    animation: 'intro-ring-expand 2s ease-out infinite',
                }}
            />
            {/* 各节点 */}
            {nodes.map((n, i) => (
                <g
                    key={`node-${i}`}
                    style={{
                        opacity: 0,
                        animation: `intro-node-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) ${0.5 + i * 0.15}s forwards`,
                    }}
                >
                    <circle cx={n.x} cy={n.y} r="5" fill="var(--card)" stroke={n.color} strokeWidth="1.2" />
                    <circle cx={n.x} cy={n.y} r="2" fill={n.color} />
                </g>
            ))}
        </svg>
    );
};

// ============================================================
// 场景可视化：雷达图（六维估值）
// ============================================================

const RadarViz: React.FC = () => {
    const center = 50;
    const maxR = 38;
    const sides = 6;
    const values = [0.85, 0.7, 0.9, 0.6, 0.8, 0.75];
    const labels = ['DCF', 'RI', '相对', 'SOTP', 'WACC', '融合'];

    const angle = (i: number) => (Math.PI * 2 * i) / sides - Math.PI / 2;
    const point = (i: number, r: number) => ({
        x: center + Math.cos(angle(i)) * r,
        y: center + Math.sin(angle(i)) * r,
    });

    const gridLevels = [0.33, 0.66, 1.0];

    return (
        <svg viewBox="0 0 100 100" className="w-full h-full">
            {/* 网格 */}
            {gridLevels.map((level, li) => {
                const pts = Array.from({ length: sides }, (_, i) => {
                    const p = point(i, maxR * level);
                    return `${p.x},${p.y}`;
                }).join(' ');
                return (
                    <polygon
                        key={`grid-${li}`}
                        points={pts}
                        fill="none"
                        stroke="var(--brand-200)"
                        strokeWidth="0.4"
                        style={{
                            opacity: 0,
                            animation: `intro-fade-in 0.4s ease-out ${li * 0.1}s forwards`,
                        }}
                    />
                );
            })}
            {/* 轴线 */}
            {Array.from({ length: sides }, (_, i) => {
                const p = point(i, maxR);
                return (
                    <line
                        key={`axis-${i}`}
                        x1={center}
                        y1={center}
                        x2={p.x}
                        y2={p.y}
                        stroke="var(--brand-200)"
                        strokeWidth="0.4"
                        style={{
                            opacity: 0,
                            animation: `intro-fade-in 0.4s ease-out ${0.3 + i * 0.05}s forwards`,
                        }}
                    />
                );
            })}
            {/* 数据多边形 */}
            <polygon
                points={values
                    .map((v, i) => {
                        const p = point(i, maxR * v);
                        return `${p.x},${p.y}`;
                    })
                    .join(' ')}
                fill="var(--brand-500)"
                fillOpacity="0.2"
                stroke="var(--brand-600)"
                strokeWidth="1"
                style={{
                    opacity: 0,
                    transformOrigin: '50px 50px',
                    animation: 'intro-radar-in 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) 0.6s forwards',
                }}
            />
            {/* 数据点 */}
            {values.map((v, i) => {
                const p = point(i, maxR * v);
                return (
                    <circle
                        key={`pt-${i}`}
                        cx={p.x}
                        cy={p.y}
                        r="1.5"
                        fill="var(--brand-600)"
                        style={{
                            opacity: 0,
                            animation: `intro-dot-in 0.3s ease-out ${1 + i * 0.08}s forwards`,
                        }}
                    />
                );
            })}
            {/* 标签 */}
            {labels.map((label, i) => {
                const p = point(i, maxR + 8);
                return (
                    <text
                        key={`label-${i}`}
                        x={p.x}
                        y={p.y}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fontSize="4"
                        fill="var(--muted-foreground)"
                        style={{
                            opacity: 0,
                            animation: `intro-fade-in 0.4s ease-out ${1.2 + i * 0.06}s forwards`,
                            fontFamily: 'var(--font-sans)',
                        }}
                    >
                        {label}
                    </text>
                );
            })}
        </svg>
    );
};

// ============================================================
// 场景可视化：盾牌脉冲
// ============================================================

const ShieldViz: React.FC = () => {
    return (
        <svg viewBox="0 0 100 100" className="w-full h-full">
            <defs>
                <linearGradient id="shieldGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--brand-500)" />
                    <stop offset="100%" stopColor="var(--brand-600)" />
                </linearGradient>
            </defs>
            {/* 脉冲环 */}
            {[0, 1, 2].map((i) => (
                <circle
                    key={i}
                    cx="50"
                    cy="50"
                    r="20"
                    fill="none"
                    stroke="var(--brand-500)"
                    strokeWidth="0.8"
                    style={{
                        transformOrigin: '50px 50px',
                        animation: `intro-shield-ring 2.5s ease-out ${i * 0.8}s infinite`,
                    }}
                />
            ))}
            {/* 盾牌 */}
            <path
                d="M 50 25 L 70 32 L 70 52 Q 70 68 50 78 Q 30 68 30 52 L 30 32 Z"
                fill="url(#shieldGrad)"
                style={{
                    transformOrigin: '50px 50px',
                    animation: 'intro-shield-in 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s both',
                }}
            />
            {/* 对勾 */}
            <path
                d="M 40 50 L 47 57 L 62 42"
                fill="none"
                stroke="var(--card)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{
                    strokeDasharray: 30,
                    strokeDashoffset: 30,
                    animation: 'intro-draw-line 0.5s ease-out 0.8s forwards',
                }}
            />
        </svg>
    );
};

// ============================================================
// 场景可视化容器
// ============================================================

const SceneViz: React.FC<{ sceneId: SceneId }> = ({ sceneId }) => {
    const viz = () => {
        switch (sceneId) {
            case 'title':
                return <LineChartViz />;
            case 'data':
                return <BarChartViz />;
            case 'agents':
                return <AgentNetworkViz />;
            case 'valuation':
                return <RadarViz />;
            case 'risk':
                return <ShieldViz />;
        }
    };

    return (
        <div
            key={sceneId}
            className="w-64 h-64 md:w-80 md:h-80"
            style={{
                animation: 'intro-viz-in 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)',
            }}
        >
            {viz()}
        </div>
    );
};

// ============================================================
// 数字滚动组件
// ============================================================

const CountUp: React.FC<{ end: number; suffix?: string; duration?: number }> = ({
    end,
    suffix = '',
    duration = 1500,
}) => {
    const [count, setCount] = useState(0);
    useEffect(() => {
        let raf: number;
        const start = performance.now();
        const tick = (now: number) => {
            const elapsed = now - start;
            const progress = Math.min(1, elapsed / duration);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.floor(eased * end));
            if (progress < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [end, duration]);
    return (
        <span>
            {count}
            {suffix}
        </span>
    );
};

// ============================================================
// 主组件
// ============================================================

export const IntroAnimation: React.FC<{ onComplete: () => void }> = ({ onComplete }) => {
    const [sceneIdx, setSceneIdx] = useState(0);
    const [exiting, setExiting] = useState(false);
    const [progress, setProgress] = useState(0);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const startTimeRef = useRef<number>(0);

    const advance = useCallback(() => {
        setSceneIdx((prev) => Math.min(prev + 1, SCENES.length - 1));
        startTimeRef.current = Date.now();
    }, []);

    const finish = useCallback(() => {
        setExiting(true);
        setTimeout(() => {
            try {
                sessionStorage.setItem(INTRO_SEEN_KEY, '1');
            } catch {
                // ignore
            }
            onComplete();
        }, 800);
    }, [onComplete]);

    useEffect(() => {
        if (startTimeRef.current === 0) {
            startTimeRef.current = Date.now();
        }
        if (sceneIdx >= SCENES.length - 1) {
            const t = setTimeout(finish, SCENE_DURATION + 1000);
            return () => clearTimeout(t);
        }
        timerRef.current = setTimeout(advance, SCENE_DURATION);
        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, [sceneIdx, advance, finish]);

    useEffect(() => {
        let raf: number;
        const tick = () => {
            const elapsed = Date.now() - startTimeRef.current;
            const pct = Math.min(100, (elapsed / SCENE_DURATION) * 100);
            setProgress(pct);
            raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [sceneIdx]);

    const currentScene = SCENES[sceneIdx];
    const isLastScene = sceneIdx === SCENES.length - 1;

    return (
        <div
            className={`fixed inset-0 z-[300] flex items-center justify-center overflow-hidden transition-all duration-700 ${
                exiting ? 'opacity-0 scale-105' : 'opacity-100 scale-100'
            }`}
            style={{
                background:
                    'radial-gradient(ellipse at 30% 20%, var(--brand-50) 0%, var(--background) 50%, var(--brand-100) 100%)',
            }}
        >
            {/* 背景装饰光斑 */}
            <div className="absolute inset-0 pointer-events-none">
                <div
                    className="absolute rounded-full blur-3xl opacity-20"
                    style={{
                        width: '600px',
                        height: '600px',
                        background: 'var(--brand-500)',
                        top: '-10%',
                        left: '-5%',
                        animation: 'intro-float 14s ease-in-out infinite',
                    }}
                />
                <div
                    className="absolute rounded-full blur-3xl opacity-15"
                    style={{
                        width: '500px',
                        height: '500px',
                        background: 'var(--chart-5)',
                        bottom: '-10%',
                        right: '-5%',
                        animation: 'intro-float 18s ease-in-out infinite reverse',
                    }}
                />
            </div>

            {/* 主内容 */}
            <div className="relative z-10 flex flex-col items-center px-8 max-w-3xl w-full">
                {/* 场景指示器 */}
                <div className="flex gap-2 mb-12">
                    {SCENES.map((_, i) => (
                        <div
                            key={i}
                            className="h-1 rounded-full transition-all duration-500"
                            style={{
                                width: i === sceneIdx ? '48px' : '16px',
                                background:
                                    i < sceneIdx
                                        ? 'var(--brand-400)'
                                        : i === sceneIdx
                                        ? 'var(--brand-600)'
                                        : 'var(--brand-200)',
                            }}
                        />
                    ))}
                </div>

                {/* 场景可视化 */}
                <SceneViz sceneId={currentScene.id} />

                {/* 图标 + 标题行 */}
                <div
                    key={`header-${sceneIdx}`}
                    className="flex items-center gap-3 mt-8 mb-3"
                    style={{
                        animation: 'intro-text-up 0.6s ease-out 0.2s both',
                    }}
                >
                    <div
                        className="flex items-center justify-center"
                        style={{
                            width: '40px',
                            height: '40px',
                            borderRadius: '50%',
                            background: 'var(--card)',
                            color: 'var(--brand-600)',
                            boxShadow: '0 4px 16px rgba(59, 53, 43, 0.1)',
                        }}
                    >
                        {currentScene.icon}
                    </div>
                    <h1
                        className="text-4xl md:text-5xl font-serif font-semibold"
                        style={{
                            color: 'var(--brand-600)',
                            letterSpacing: '-0.02em',
                            background:
                                'linear-gradient(135deg, var(--brand-600) 0%, var(--brand-500) 100%)',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                            backgroundClip: 'text',
                        }}
                    >
                        {currentScene.title}
                    </h1>
                </div>

                {/* 副标题 */}
                <p
                    key={`subtitle-${sceneIdx}`}
                    className="text-base md:text-lg text-center max-w-xl leading-relaxed"
                    style={{
                        color: 'var(--muted-foreground)',
                        animation: 'intro-text-up 0.6s ease-out 0.35s both',
                    }}
                >
                    {currentScene.subtitle}
                </p>

                {/* 数据指标（特定场景显示） */}
                {currentScene.id === 'data' && (
                    <div
                        className="flex gap-8 mt-8"
                        style={{ animation: 'intro-text-up 0.6s ease-out 0.5s both' }}
                    >
                        <div className="text-center">
                            <div
                                className="text-2xl font-serif font-semibold"
                                style={{ color: 'var(--brand-600)' }}
                            >
                                <CountUp end={6} /> 维
                            </div>
                            <div className="text-xs text-[var(--muted-foreground)] mt-1">财务分析</div>
                        </div>
                        <div className="text-center">
                            <div
                                className="text-2xl font-serif font-semibold"
                                style={{ color: 'var(--brand-600)' }}
                            >
                                <CountUp end={4} /> 表
                            </div>
                            <div className="text-xs text-[var(--muted-foreground)] mt-1">核心报表</div>
                        </div>
                        <div className="text-center">
                            <div
                                className="text-2xl font-serif font-semibold"
                                style={{ color: 'var(--brand-600)' }}
                            >
                                <CountUp end={5000} suffix="+" />
                            </div>
                            <div className="text-xs text-[var(--muted-foreground)] mt-1">A股覆盖</div>
                        </div>
                    </div>
                )}

                {currentScene.id === 'valuation' && (
                    <div
                        className="flex gap-6 mt-8"
                        style={{ animation: 'intro-text-up 0.6s ease-out 0.5s both' }}
                    >
                        {['DCF', 'RI', '相对', 'SOTP', 'WACC', '融合'].map((m, i) => (
                            <span
                                key={m}
                                className="text-xs font-medium px-3 py-1 rounded-full"
                                style={{
                                    background: 'var(--brand-100)',
                                    color: 'var(--brand-600)',
                                    animation: `intro-dot-in 0.3s ease-out ${0.6 + i * 0.08}s both`,
                                }}
                            >
                                {m}
                            </span>
                        ))}
                    </div>
                )}

                {/* 进入按钮（最后一场景） */}
                {isLastScene && (
                    <button
                        onClick={finish}
                        className="mt-10 flex items-center gap-2 px-8 py-3 rounded-vibe-sm font-medium transition-all hover:scale-105 active:scale-95"
                        style={{
                            background: 'linear-gradient(135deg, var(--brand-600) 0%, var(--brand-500) 100%)',
                            color: 'var(--primary-foreground)',
                            animation: 'intro-text-up 0.6s ease-out 0.6s both',
                            boxShadow: '0 8px 32px rgba(59, 53, 43, 0.3)',
                        }}
                    >
                        进入工作台
                        <ArrowRight className="w-4 h-4" />
                    </button>
                )}

                {/* 进度条 */}
                {!isLastScene && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--brand-200)]">
                        <div
                            className="h-full"
                            style={{
                                width: `${progress}%`,
                                background: 'linear-gradient(90deg, var(--brand-500), var(--brand-600))',
                                transition: 'none',
                            }}
                        />
                    </div>
                )}
            </div>

            {/* 跳过按钮 */}
            <button
                onClick={finish}
                className="absolute bottom-8 right-8 flex items-center gap-1.5 text-sm transition-opacity hover:opacity-100"
                style={{
                    color: 'var(--muted-foreground)',
                    opacity: 0.5,
                }}
            >
                跳过
                <ArrowRight className="w-3.5 h-3.5" />
            </button>

            <style>{`
                @keyframes intro-float {
                    0%, 100% { transform: translate(0, 0) scale(1); }
                    33% { transform: translate(40px, -50px) scale(1.08); }
                    66% { transform: translate(-30px, 40px) scale(0.92); }
                }
                @keyframes intro-text-up {
                    0% { opacity: 0; transform: translateY(20px); }
                    100% { opacity: 1; transform: translateY(0); }
                }
                @keyframes intro-viz-in {
                    0% { opacity: 0; transform: scale(0.7); }
                    100% { opacity: 1; transform: scale(1); }
                }
                @keyframes intro-fade-in {
                    0% { opacity: 0; }
                    100% { opacity: 1; }
                }
                @keyframes intro-draw-line {
                    to { stroke-dashoffset: 0; }
                }
                @keyframes intro-area-in {
                    0% { opacity: 0; }
                    100% { opacity: 1; }
                }
                @keyframes intro-dot-in {
                    0% { opacity: 0; transform: scale(0); }
                    100% { opacity: 1; transform: scale(1); }
                }
                @keyframes intro-bar-grow {
                    0% { transform: scaleY(0); }
                    100% { transform: scaleY(1); }
                }
                @keyframes intro-node-pop {
                    0% { opacity: 0; transform: scale(0); }
                    100% { opacity: 1; transform: scale(1); }
                }
                @keyframes intro-pulse {
                    0%, 100% { transform: scale(1); opacity: 1; }
                    50% { transform: scale(1.15); opacity: 0.8; }
                }
                @keyframes intro-ring-expand {
                    0% { transform: scale(1); opacity: 0.8; }
                    100% { transform: scale(3); opacity: 0; }
                }
                @keyframes intro-radar-in {
                    0% { opacity: 0; transform: scale(0); }
                    100% { opacity: 1; transform: scale(1); }
                }
                @keyframes intro-shield-in {
                    0% { opacity: 0; transform: scale(0.5); }
                    100% { opacity: 1; transform: scale(1); }
                }
                @keyframes intro-shield-ring {
                    0% { transform: scale(1); opacity: 0.6; }
                    100% { transform: scale(2.5); opacity: 0; }
                }
            `}</style>
        </div>
    );
};

export function shouldShowIntro(): boolean {
    try {
        return !sessionStorage.getItem(INTRO_SEEN_KEY);
    } catch {
        return false;
    }
}
