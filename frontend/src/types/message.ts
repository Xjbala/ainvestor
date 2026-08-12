// WebSocket消息类型定义

export type MessageType = 'system' | 'agent' | 'conference' | 'prediction' | 'report' | 'error';

export type EventType =
  | 'session_start'
  | 'session_end'
  | 'cancellation_requested'
  | 'ping'
  | 'pong'
  | 'analysis_start'
  | 'analysis_progress'
  | 'analysis_complete'
  | 'analysis_failed'
  | 'conference_start'
  | 'round_start'
  | 'message'
  | 'round_end'
  | 'conference_end'
  | 'summary'
  | 'prediction_update'
  | 'report_generated'
  | 'error';

export interface CommandErrorData extends Record<string, unknown> {
  error?: string;
  details?: string;
  command?: string;
}

export interface WebSocketMessage {
  type: MessageType;
  event: EventType;
  data: CommandErrorData;
  session_id?: string;
  timestamp: string;
  message_id: string;
}

export interface AgentData {
  agent_id: string;
  content: string;
  phase?: string;
  progress?: number;
}

export interface ConferenceData {
  agent_id?: string;
  content?: string;
  round?: number;
  total_rounds?: number;
}

export interface PredictionData {
  agent_id: string;
  predictions: Prediction[];
}

export interface Prediction {
  ticker: string;
  direction: 'up' | 'down' | 'neutral';
  confidence: number;
}

export interface SessionData {
  tickers: string[];
  date: string;
}

// Agent状态
export interface AgentState {
  id: string;
  name: string;
  status: 'idle' | 'analyzing' | 'complete' | 'error';
  content: string;
  progress: number;
  phase: string;
}

// 会议消息
export interface ConferenceMessage {
  id: string;
  agent_id: string;
  content: string;
  timestamp: string;
  phase?: string;
}

// 分析会话状态
export interface AnalysisSession {
  id: string | null;
  tickers: string[];
  date: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';
  agents: Record<string, AgentState>;
  conferenceMessages: ConferenceMessage[];
  predictions: Record<string, Prediction[]>;
  report: string;
  currentRound: number;
  totalRounds: number;
}
