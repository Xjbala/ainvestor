import { useState, useEffect, useMemo, useRef } from 'react';
import { ToastProvider } from './components/Common/Toast';
import { useWebSocket } from './hooks/useWebSocket';
import { createStartAnalysisCommand, createStopAnalysisCommand } from './hooks/useWebSocket';
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

// WebSocket服务器地址 - 使用相对路径以适应不同部署环境
const WS_URL = import.meta.env.VITE_WS_URL || 
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8765`;

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

  // 包装的mode切换函数，支持设置ticker
  const handleSwitchMode = (newMode: 'dashboard' | 'ai' | 'expert' | 'reports' | 'data' | 'dataView' | 'stocks', ticker?: string) => {
    setMode(newMode);
    if (ticker) {
      setCurrentTicker(ticker);
    }
  };

  // Stock list analysis handlers
  const handleStockAnalyzeAI = (ticker: string) => {
    const command = createStartAnalysisCommand([ticker], new Date().toISOString().split('T')[0]);
    send(command);
    dispatch({
      type: 'SESSION_START',
      payload: { id: `local-${Date.now()}`, tickers: [ticker], date: new Date().toISOString() }
    });
    setMode('ai');
  };

  const handleStockAnalyzeExpert = (ticker: string) => {
    setCurrentTicker(ticker);
    setMode('expert');
  };

  // Track if we've connected before to detect reconnections
  const hasConnectedBefore = useRef(false);

  const { connect, send } = useWebSocket({
    url: WS_URL,
    onMessage: handleMessage,
    onOpen: () => {
      console.log('Connected to analysis server');
      if (hasConnectedBefore.current && state.status === 'running') {
        console.log('[Session Sync] Server reconnected, resetting running state');
        dispatch({ type: 'SESSION_END', payload: { success: false } });
      }
      hasConnectedBefore.current = true;
    },
    onClose: () => console.log('Disconnected from analysis server'),
  });

  // WebSocket connection effect
  useEffect(() => {
    connect();
  }, [connect]);

  // Stop analysis handler
  const handleStopAnalysis = () => {
    send(createStopAnalysisCommand());
    dispatch({ type: 'SESSION_END', payload: { success: false } });
  };

  // Auto-load last session
  useEffect(() => {
    console.log('[Session Restore] Effect triggered, state.id:', state.id);
    if (state.id) {
      console.log('[Session Restore] Session already loaded, skipping');
      return;
    }

    const fetchLastSession = async () => {
      try {
        const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        console.log('[Session Restore] Fetching sessions from:', `${API_URL}/api/sessions?limit=1`);

        const res = await fetch(`${API_URL}/api/sessions?limit=1`);
        if (!res.ok) {
          throw new Error(`Failed to fetch sessions: ${res.status} ${res.statusText}`);
        }
        const sessions = await res.json();
        console.log('[Session Restore] Sessions response:', sessions);

        if (sessions && sessions.length > 0) {
          const session = sessions[0];
          console.log('[Session Restore] Found previous session:', session);

          // Fetch outputs
          console.log('[Session Restore] Fetching outputs for session:', session.id);
          const outputsRes = await fetch(`${API_URL}/api/sessions/${session.id}/outputs`);
          if (!outputsRes.ok) {
            throw new Error(`Failed to fetch outputs: ${outputsRes.status} ${outputsRes.statusText}`);
          }
          const outputs = await outputsRes.json();
          console.log('[Session Restore] Outputs:', outputs);

          // Fetch report if completed
          let report = '';
          if (session.status === 'completed') {
            try {
              console.log('[Session Restore] Fetching report for completed session');
              const reportRes = await fetch(`${API_URL}/api/sessions/${session.id}/report`);
              if (reportRes.ok) {
                const reportData = await reportRes.json();
                report = reportData.report_content;
                console.log('[Session Restore] Report fetched, length:', report?.length);
              } else {
                console.log('[Session Restore] Report fetch failed:', reportRes.status, reportRes.statusText);
              }
            } catch (e) {
              console.log('[Session Restore] No report found for completed session:', e);
            }
          }

          console.log('[Session Restore] Dispatching RESTORE_SESSION action');
          dispatch({
            type: 'RESTORE_SESSION',
            payload: {
              session: { ...session, report },
              outputs
            }
          });
          console.log('[Session Restore] Session restored successfully');
        } else {
          console.log('[Session Restore] No previous sessions found');
        }
      } catch (e) {
        console.error('[Session Restore] Failed to load last session:', e);
      }
    };

    fetchLastSession();
  }, []); // Run once on mount

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
      .filter(agent => agent.status !== 'idle' && agent.status !== 'error' && agent.content)
      .map(agent => ({
        id: `agent-${agent.id}`,
        agentName: agent.name || getDisplayName(agent.id),
        content: agent.content || '',
        timestamp: new Date().toISOString(),
        type: (agent.status === 'analyzing' ? 'info' : 'success') as 'info' | 'success',
      }));

    const confMessages = state.conferenceMessages.map(msg => ({
      id: msg.id,
      agentName: getDisplayName(msg.agent_id), // Map agent_id to name
      content: msg.content,
      timestamp: msg.timestamp,
      type: 'info' as const, // Default type for conference
    }));

    // Sort by timestamp if needed, otherwise just append
    return [...agentMessages, ...confMessages];
  }, [agentList, state.conferenceMessages]);


  // ========================================
  // Render
  // ========================================

  return (
    <ToastProvider>
    <div className="flex bg-gray-50 text-gray-900 font-sans min-h-screen">
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
    </ToastProvider>
  );
}

export default App;
