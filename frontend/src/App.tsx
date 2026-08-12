import { useState, useEffect, useMemo, useRef } from 'react';
import { useToast } from './components/Common/Toast';
import { useWebSocket } from './hooks/useWebSocket';
import { createStartAnalysisCommand, createStopAnalysisCommand, createResumeAnalysisCommand } from './hooks/useWebSocket';
import { useAnalysisStore } from './stores/analysisStore';
import { useModeStore } from './stores/modeStore';
import { Sidebar } from './components/Sidebar'; // Layout/Sidebar logic
import { Workstation } from './components/Dashboard'; // Dashboard view
import { ExpertDashboard } from './components/ExpertMode';
import { AIModeLayout } from './components/AIMode/AIModeLayout';
import { DataManagement } from './components/DataManagement/DataManagement';
import { DataViewer } from './components/DataViewer/DataViewer';
import { StockList } from './components/StockList/StockList';
import { ReportsPage } from './components/Reports/ReportsPage';
import { extractInvestmentRecommendations } from './utils/metricExtraction';

// WebSocket服务器地址 - 使用相对路径以适应不同部署环境
const WS_URL = import.meta.env.VITE_WS_URL || 
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8765`;
const ACTIVE_SESSION_STORAGE_KEY = 'ainvestor.activeAnalysisSessionId';

function getStoredActiveSessionId(): string | null {
  try {
    return window.sessionStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeActiveSessionId(sessionId: string | null) {
  try {
    if (sessionId) {
      window.sessionStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, sessionId);
    } else {
      window.sessionStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
    }
  } catch {
    // 会话存储不可用时仍保留当前页面内的连接恢复能力。
  }
}

function App() {
  // 当前正在分析的股票代码（用于专家模式）
  const [currentTicker, setCurrentTicker] = useState<string | undefined>(undefined);

  const {
    state,
    handleMessage,
    agentList,
    dispatch,
    metrics,
  } = useAnalysisStore();

  /*
   * Mode Management
   * We use the mode store to switch between Dashboard, AI, Expert, etc.
   */
  const { mode, setMode } = useModeStore();
  const toast = useToast();

  // 包装的mode切换函数，支持设置ticker
  const handleSwitchMode = (newMode: 'dashboard' | 'ai' | 'expert' | 'reports' | 'data' | 'dataView' | 'stocks', ticker?: string) => {
    setMode(newMode);
    if (ticker) {
      setCurrentTicker(ticker);
    }
  };

  // Stock list analysis handlers
  const handleStockAnalyzeAI = (ticker: string) => {
    send(createStartAnalysisCommand([ticker], new Date().toISOString().split('T')[0]));
    setMode('ai');
  };

  const handleStockAnalyzeExpert = (ticker: string) => {
    setCurrentTicker(ticker);
    setMode('expert');
  };

  // Track the current analysis across WebSocket reconnects and page refreshes.
  const activeSessionIdRef = useRef<string | null>(getStoredActiveSessionId());
  const [isStopRequested, setIsStopRequested] = useState(false);

  const { connect, send } = useWebSocket({
    url: WS_URL,
    onMessage: (message) => {
      if (message.event === 'session_start') {
        activeSessionIdRef.current = message.session_id || null;
        storeActiveSessionId(activeSessionIdRef.current);
        setIsStopRequested(false);
      }
      if (message.event === 'session_end') {
        activeSessionIdRef.current = null;
        storeActiveSessionId(null);
        setIsStopRequested(false);
      }
      if (message.event === 'cancellation_requested') {
        setIsStopRequested(true);
      }
      if (message.event === 'error') {
        const error = typeof message.data.error === 'string'
          ? message.data.error
          : '分析服务返回未知错误';
        const details = typeof message.data.details === 'string'
          ? message.data.details
          : '';
        const command = typeof message.data.command === 'string'
          ? message.data.command
          : '';
        toast.error(details ? `${error}: ${details}` : error);
        setIsStopRequested(false);
        if (error === 'Analysis session is not running' && message.session_id === activeSessionIdRef.current) {
          activeSessionIdRef.current = null;
          storeActiveSessionId(null);
          dispatch({ type: 'SESSION_END', payload: { success: false, status: 'failed' } });
        }
        if (command) {
          return;
        }
      }
      handleMessage(message);
    },
    onOpen: () => {
      console.log('Connected to analysis server');
      if (activeSessionIdRef.current) {
        console.log('[Session Sync] Resuming active analysis session');
        send(createResumeAnalysisCommand(activeSessionIdRef.current));
      }
    },
    onClose: () => {
      console.log('Disconnected from analysis server');
      setIsStopRequested(false);
    },
  });

  // WebSocket connection effect
  useEffect(() => {
    connect();
  }, [connect]);

  // Stop analysis handler
  const handleStopAnalysis = () => {
    const sessionId = activeSessionIdRef.current;
    if (!sessionId) {
      toast.error('没有可停止的分析会话，请刷新后重试');
      return;
    }
    if (isStopRequested) {
      return;
    }
    if (!send(createStopAnalysisCommand(sessionId))) {
      toast.error('分析服务未连接，无法停止会话');
      return;
    }
    setIsStopRequested(true);
  };

  // 历史会话仅在工作台和报告页按需加载，避免覆盖实时协作状态。


  // Combine agent analysis outputs with conference messages for the feed
  const feedMessages = useMemo(() => {
    const getDisplayName = (id: string) => {
      const names: Record<string, string> = {
        fundamentals_analyst: '基本面分析师',
        valuation_analyst: '估值分析师',
        technical_analyst: '技术分析师',
        sentiment_analyst: '情绪分析师',
        risk_manager: '风险管理',
        portfolio_manager: '投资顾问',
      };
      return names[id] || id;
    };

    const agentMessages = agentList
      .filter(agent => agent.status !== 'idle' && agent.content)
      .map(agent => ({
        id: `agent-${agent.id}`,
        agentId: agent.id,
        agentName: agent.name || getDisplayName(agent.id),
        content: agent.content || '',
        timestamp: new Date().toISOString(),
        type: (
          agent.status === 'error'
            ? 'alert'
            : agent.status === 'analyzing'
              ? 'info'
              : 'success'
        ) as 'info' | 'success' | 'alert',
      }));

    const confMessages = state.conferenceMessages.map(msg => ({
      id: msg.id,
      agentId: msg.agent_id,
      agentName: getDisplayName(msg.agent_id), // Map agent_id to name
      content: msg.content,
      timestamp: msg.timestamp,
      type: 'info' as const, // Default type for conference
    }));

    const portfolioDecision = agentMessages.find(
      message => message.agentId === 'portfolio_manager'
        && extractInvestmentRecommendations(message.content),
    );
    const nonDecisionAgentMessages = agentMessages.filter(
      message => message !== portfolioDecision,
    );

    // PM 的最终建议置于会议讨论之后，自动滚动时始终可见。
    return portfolioDecision
      ? [...nonDecisionAgentMessages, ...confMessages, portfolioDecision]
      : [...nonDecisionAgentMessages, ...confMessages];
  }, [agentList, state.conferenceMessages]);


  // ========================================
  // Render
  // ========================================

  return (
    <div className="flex bg-background text-foreground font-sans min-h-screen">
      {/* Global Sidebar (Left Navigation) */}
      <Sidebar activeMode={mode} onSwitchMode={setMode} />

      {/* Main Content Area */}
      <main className="flex-1 ml-16 relative min-h-screen flex flex-col">

        {/* DASHBOARD MODE */}
        {mode === 'dashboard' && (
          <Workstation onSwitchMode={handleSwitchMode} onSendCommand={send} dispatch={dispatch} />
        )}

        {/* AI MODE */}
        {mode === 'ai' && (
          <AIModeLayout
            ticker={state.tickers[0] || '600519'}
            agents={agentList}
            messages={feedMessages}
            metrics={metrics}
            report={state.report}
            analysisStatus={state.status}
            onStopAnalysis={handleStopAnalysis}
            isStopRequested={isStopRequested}
          />
        )}

        {/* EXPERT MODE */}
        {mode === 'expert' && (
          <main className="app-main expert-mode flex-1 p-6">
            <ExpertDashboard ticker={currentTicker} />
          </main>
        )}

        {/* STOCKS MODE */}
        {mode === 'stocks' && (
          <main className="app-main stocks-mode flex-1 p-6">
            <StockList onAnalyzeAI={handleStockAnalyzeAI} onAnalyzeExpert={handleStockAnalyzeExpert} />
          </main>
        )}

        {/* DATA COLLECTION MODE */}
        {mode === 'data' && (
          <main className="app-main data-mode flex-1 p-6">
            <DataManagement />
          </main>
        )}

        {/* DATA VIEW MODE */}
        {mode === 'dataView' && (
          <main className="app-main dataView-mode flex-1 p-6">
            <DataViewer />
          </main>
        )}

        {/* REPORTS MODE */}
        {mode === 'reports' && (
          <main className="app-main reports-mode flex-1 p-6">
            <ReportsPage onSwitchMode={(m) => setMode(m as 'dashboard' | 'ai' | 'expert' | 'reports' | 'data' | 'dataView' | 'stocks')} />
          </main>
        )}

      </main>
    </div>
  );
}

export default App;
