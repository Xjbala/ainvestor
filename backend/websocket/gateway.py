# -*- coding: utf-8 -*-
"""
WebSocket网关

管理WebSocket连接，处理消息路由
"""

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Callable, Dict, List, Optional

import websockets
from websockets.server import WebSocketServerProtocol, serve

from .message import (
    WebSocketMessage,
    MessageType,
    EventType,
    create_cancellation_requested_message,
    create_error_message,
    create_session_start_message,
)
from .state_sync import WebSocketStateSync

logger = logging.getLogger(__name__)

# A股股票代码正则: 6位数字
_A_SHARE_PATTERN = re.compile(r'^[0-9]\d{5}$')


def _validate_tickers(tickers: List[str]) -> Optional[str]:
    """
    校验股票代码列表

    Args:
        tickers: 股票代码列表

    Returns:
        错误信息，如果校验通过则返回 None
    """
    if not tickers or not isinstance(tickers, list):
        return "tickers 必须是非空列表"

    if len(tickers) > 10:
        return "单次分析最多支持 10 只股票"

    for ticker in tickers:
        if not isinstance(ticker, str):
            return f"股票代码必须是字符串，收到: {type(ticker).__name__}"
        ticker = ticker.strip()
        if not ticker:
            return "股票代码不能为空字符串"
        if not _A_SHARE_PATTERN.match(ticker):
            return f"无效的A股股票代码: '{ticker}'（应为6位数字，如 000001, 600519）"

    return None


class WebSocketGateway:
    """
    WebSocket网关
    
    功能：
    - 管理客户端连接
    - 消息路由
    - 心跳检测
    - 触发分析任务
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        state_sync: Optional[WebSocketStateSync] = None,
    ):
        self.host = host
        self.port = port
        self.state_sync = state_sync or WebSocketStateSync()
        self._server = None
        self._analysis_handler: Optional[Callable] = None
        self._running = False
        self._current_tasks: Dict[str, asyncio.Task] = {}
        self._session_syncs: Dict[str, WebSocketStateSync] = {}
        self._client_sessions: Dict[WebSocketServerProtocol, str] = {}
        self._session_metadata: Dict[str, Dict[str, Any]] = {}
    
    def set_analysis_handler(self, handler: Callable):
        """
        设置分析任务处理器
        
        handler签名: async def handler(tickers: list, date: str, session_id: str) -> None
        """
        self._analysis_handler = handler
    
    async def bind(self):
        """Bind the WebSocket listener without blocking on its shutdown."""
        self._running = True
        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
        )
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")

    async def start(self):
        """启动WebSocket服务器并保持运行。"""
        await self.bind()
        await self.wait_closed()

    async def wait_closed(self):
        """Wait until the bound WebSocket server stops."""
        await self._server.wait_closed()
    
    async def stop(self):
        """停止WebSocket服务器"""
        self._running = False
        tasks = [task for task in self._current_tasks.values() if not task.done()]
        if tasks:
            logger.info("Cancelling %s active analysis task(s)", len(tasks))
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket server stopped")
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol):
        """处理客户端连接。"""
        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client connection closed")
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
        finally:
            session_id = self._client_sessions.pop(websocket, None)
            if session_id:
                session_sync = self._session_syncs.get(session_id)
                if session_sync:
                    await session_sync.unregister(websocket)
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, raw_message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(raw_message)
            msg_type = data.get("type", "")
            event = data.get("event", "")
            
            # 处理心跳
            if msg_type == "ping" or event == "ping":
                await websocket.send(json.dumps({
                    "type": "system",
                    "event": "pong",
                    "timestamp": WebSocketMessage(
                        type=MessageType.SYSTEM,
                        event=EventType.PONG,
                    ).timestamp,
                }))
                return
            
            # 处理开始分析请求
            if msg_type == "command" and event == "start_analysis":
                await self._handle_start_analysis(websocket, data)
                return
            
            # 处理停止分析请求
            if msg_type == "command" and event == "stop_analysis":
                await self._handle_stop_analysis(websocket, data)
                return

            # 处理分析会话重连请求
            if msg_type == "command" and event == "resume_analysis":
                await self._handle_resume_analysis(websocket, data)
                return

            logger.debug(f"Received message: {data}")
            
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON message: {e}")
            error_msg = create_error_message(
                session_id="",
                error="Invalid message format",
                details=str(e),
            )
            await websocket.send(error_msg.to_json())
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_msg = create_error_message(
                session_id="",
                error="Internal error",
                details=str(e),
            )
            await websocket.send(error_msg.to_json())
    
    async def _handle_start_analysis(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]):
        """处理开始分析请求"""
        tickers = data.get("data", {}).get("tickers", [])
        date = data.get("data", {}).get("date", "")

        if not tickers:
            error_msg = create_error_message(
                session_id="",
                error="Missing tickers",
                details="Please provide at least one ticker symbol",
            )
            await websocket.send(error_msg.to_json())
            return

        # 校验股票代码格式
        validation_error = _validate_tickers(tickers)
        if validation_error:
            error_msg = create_error_message(
                session_id="",
                error="Invalid tickers",
                details=validation_error,
            )
            await websocket.send(error_msg.to_json())
            return

        # 校验日期格式
        if date:
            import re as _re
            if not _re.match(r'^\d{4}-\d{2}-\d{2}$', date):
                error_msg = create_error_message(
                    session_id="",
                    error="Invalid date",
                    details=f"日期格式错误: '{date}'（应为 YYYY-MM-DD）",
                )
                await websocket.send(error_msg.to_json())
                return
        
        # 如果未配置分析处理器，不创建无法执行的会话。
        if not self._analysis_handler:
            error_msg = create_error_message(
                session_id="",
                error="Analysis handler not configured",
            )
            await websocket.send(error_msg.to_json())
            return

        # 生成独立会话和同步器，避免并发分析覆盖其他会话的 session_id。
        session_id = str(uuid.uuid4())
        session_sync = WebSocketStateSync(session_id=session_id)
        await session_sync.register(websocket)
        self._session_syncs[session_id] = session_sync
        self._client_sessions[websocket] = session_id
        self._session_metadata[session_id] = {
            "tickers": tickers,
            "date": date,
            "started": False,
        }
        logger.info(
            "start_analysis received: session=%s tickers=%s client=%s",
            session_id,
            tickers,
            getattr(websocket, "remote_address", None),
        )
        await session_sync.on_session_start(tickers, date)

        # 异步启动分析任务
        task = asyncio.create_task(
            self._run_analysis(tickers, date, session_id, session_sync)
        )
        self._current_tasks[session_id] = task
    
    def _cleanup_session(self, session_id: str):
        """清理已结束分析会话的运行时状态。"""
        self._current_tasks.pop(session_id, None)
        self._session_syncs.pop(session_id, None)
        self._session_metadata.pop(session_id, None)
        for client, client_session_id in list(self._client_sessions.items()):
            if client_session_id == session_id:
                self._client_sessions.pop(client, None)

    async def _run_analysis(
        self,
        tickers: list,
        date: str,
        session_id: str,
        session_sync: WebSocketStateSync,
    ):
        """运行单个会话的分析任务。"""
        metadata = self._session_metadata.get(session_id)
        if metadata:
            metadata["started"] = True
        try:
            await self._analysis_handler(tickers, date, session_id, session_sync)
            await session_sync.on_session_end(success=True, status="completed")
        except asyncio.CancelledError:
            logger.info("Analysis task cancelled: session=%s", session_id)
            await session_sync.on_session_end(success=False, status="cancelled")
            raise
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            error_msg = create_error_message(
                session_id=session_id,
                error="Analysis failed",
                details=str(e),
            )
            await session_sync.broadcast(error_msg)
            await session_sync.on_session_end(success=False, status="failed")
        finally:
            self._cleanup_session(session_id)
    
    async def _handle_stop_analysis(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]):
        """停止当前连接订阅的指定分析会话。"""
        command_data = data.get("data", {})
        requested_session_id = (
            command_data.get("session_id")
            if isinstance(command_data, dict)
            else None
        )
        session_id = requested_session_id if isinstance(requested_session_id, str) else ""
        bound_session_id = self._client_sessions.get(websocket)

        if not session_id:
            await websocket.send(create_error_message(
                session_id=bound_session_id or "",
                error="Missing analysis session ID",
                command="stop_analysis",
            ).to_json())
            return

        if session_id != bound_session_id:
            logger.warning(
                "Stop analysis rejected: requested=%s bound=%s client=%s",
                session_id,
                bound_session_id,
                getattr(websocket, "remote_address", None),
            )
            await websocket.send(create_error_message(
                session_id=session_id,
                error="Analysis session is not bound to this connection",
                command="stop_analysis",
            ).to_json())
            return

        task = self._current_tasks.get(session_id)
        if not task or task.done():
            logger.info("No running analysis task for requested session=%s", session_id)
            await websocket.send(create_error_message(
                session_id=session_id,
                error="Analysis session is not running",
                command="stop_analysis",
            ).to_json())
            return

        logger.info(
            "Stop analysis requested: session=%s client=%s",
            session_id,
            getattr(websocket, "remote_address", None),
        )
        session_sync = self._session_syncs.get(session_id)
        metadata = self._session_metadata.get(session_id)
        await websocket.send(create_cancellation_requested_message(session_id).to_json())
        task.cancel()
        await asyncio.sleep(0)
        if task.cancelled() and metadata and not metadata["started"]:
            logger.info("Analysis task cancelled before start: session=%s", session_id)
            if session_sync:
                await session_sync.on_session_end(success=False, status="cancelled")
            self._cleanup_session(session_id)
            return

        try:
            await task
        except asyncio.CancelledError:
            logger.info("Analysis task cancellation completed: session=%s", session_id)

    async def _handle_resume_analysis(
        self,
        websocket: WebSocketServerProtocol,
        data: Dict[str, Any],
    ):
        """将断线重连的客户端重新绑定到仍在运行的分析会话。"""
        requested_session_id = data.get("data", {}).get("session_id")
        session_id = requested_session_id if isinstance(requested_session_id, str) else ""
        task = self._current_tasks.get(session_id)
        session_sync = self._session_syncs.get(session_id)
        metadata = self._session_metadata.get(session_id)

        if not session_id or not task or task.done() or not session_sync or not metadata:
            await websocket.send(create_error_message(
                session_id=session_id,
                error="Analysis session is not running",
                command="resume_analysis",
            ).to_json())
            return

        previous_session_id = self._client_sessions.get(websocket)
        if previous_session_id and previous_session_id != session_id:
            previous_sync = self._session_syncs.get(previous_session_id)
            if previous_sync:
                await previous_sync.unregister(websocket)

        await session_sync.register(websocket)
        self._client_sessions[websocket] = session_id
        await websocket.send(create_session_start_message(
            session_id=session_id,
            tickers=metadata["tickers"],
            date=metadata["date"],
        ).to_json())
        logger.info("Analysis session resumed: session=%s", session_id)


async def run_gateway(
    host: str = "0.0.0.0",
    port: int = 8765,
    analysis_handler: Optional[Callable] = None,
) -> WebSocketGateway:
    """
    启动WebSocket网关
    
    Args:
        host: 监听地址
        port: 监听端口
        analysis_handler: 分析任务处理器
        
    Returns:
        WebSocketGateway实例
    """
    gateway = WebSocketGateway(host=host, port=port)
    
    if analysis_handler:
        gateway.set_analysis_handler(analysis_handler)
    
    await gateway.start()
    return gateway
