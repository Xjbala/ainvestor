import { useCallback, useEffect, useRef, useState } from 'react';
import type { WebSocketMessage } from '../types/message';

interface UseWebSocketOptions {
    url: string;
    onMessage?: (message: WebSocketMessage) => void;
    onOpen?: () => void;
    onClose?: () => void;
    onError?: (error: Event) => void;
    reconnectInterval?: number;
    maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
    isConnected: boolean;
    send: (data: object) => boolean;
    connect: () => void;
    disconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
    const {
        url,
        onMessage,
        onOpen,
        onClose,
        onError,
        reconnectInterval = 3000,
        maxReconnectAttempts = 5,
    } = options;

    const [isConnected, setIsConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttemptsRef = useRef(0);
    const reconnectTimeoutRef = useRef<number | null>(null);
    const shouldReconnectRef = useRef(true);
    const connectRef = useRef<() => void>(() => undefined);
    const callbacksRef = useRef({ onMessage, onOpen, onClose, onError });

    useEffect(() => {
        callbacksRef.current = { onMessage, onOpen, onClose, onError };
    }, [onMessage, onOpen, onClose, onError]);

    const connect = useCallback(() => {
        const readyState = wsRef.current?.readyState;
        if (readyState === WebSocket.OPEN || readyState === WebSocket.CONNECTING) {
            return;
        }

        shouldReconnectRef.current = true;
        try {
            const ws = new WebSocket(url);

            ws.onopen = () => {
                console.log('WebSocket connected');
                setIsConnected(true);
                reconnectAttemptsRef.current = 0;
                callbacksRef.current.onOpen?.();
            };

            ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data) as WebSocketMessage;
                    callbacksRef.current.onMessage?.(message);
                } catch (e) {
                    console.error('Failed to parse WebSocket message:', e);
                }
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
                setIsConnected(false);
                if (wsRef.current === ws) {
                    wsRef.current = null;
                }
                callbacksRef.current.onClose?.();

                if (
                    shouldReconnectRef.current
                    && reconnectAttemptsRef.current < maxReconnectAttempts
                ) {
                    reconnectAttemptsRef.current += 1;
                    console.log(`Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
                    reconnectTimeoutRef.current = window.setTimeout(
                        () => connectRef.current(),
                        reconnectInterval,
                    );
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                callbacksRef.current.onError?.(error);
            };

            wsRef.current = ws;
        } catch (e) {
            console.error('Failed to create WebSocket:', e);
        }
    }, [url, reconnectInterval, maxReconnectAttempts]);

    useEffect(() => {
        connectRef.current = connect;
    }, [connect]);

    const disconnect = useCallback(() => {
        shouldReconnectRef.current = false;
        if (reconnectTimeoutRef.current !== null) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        wsRef.current?.close();
    }, []);

    const send = useCallback((data: object): boolean => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(data));
            return true;
        }

        console.warn('WebSocket is not connected');
        return false;
    }, []);

    useEffect(() => disconnect, [disconnect]);

    return {
        isConnected,
        send,
        connect,
        disconnect,
    };
}

// 发送分析请求的辅助函数
export function createStartAnalysisCommand(tickers: string[], date?: string) {
    return {
        type: 'command',
        event: 'start_analysis',
        data: {
            tickers,
            date: date || new Date().toISOString().split('T')[0],
        },
    };
}

export function createStopAnalysisCommand(sessionId: string) {
    return {
        type: 'command',
        event: 'stop_analysis',
        data: { session_id: sessionId },
    };
}

export function createResumeAnalysisCommand(sessionId: string) {
    return {
        type: 'command',
        event: 'resume_analysis',
        data: { session_id: sessionId },
    };
}
