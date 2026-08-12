# -*- coding: utf-8 -*-
"""
WebSocket StateSync实现

实现StateSync接口，将Agent状态实时广播到前端
"""

import asyncio
import logging
from typing import Any, Optional, Set, TYPE_CHECKING

from .message import (
    WebSocketMessage,
    EventType,
    create_session_start_message,
    create_session_end_message,
    create_agent_message,
    create_conference_message,
    create_prediction_message,
    create_report_message,
)
from ..persistence.compat import get_database

if TYPE_CHECKING:
    from websockets.server import WebSocketServerProtocol

logger = logging.getLogger(__name__)


class WebSocketStateSync:
    """
    WebSocket状态同步器
    
    实现Pipeline中StateSync接口，将状态广播到所有连接的WebSocket客户端
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self._clients: Set["WebSocketServerProtocol"] = set()
        self._session_id = session_id
        self._lock = asyncio.Lock()
    
    def set_session_id(self, session_id: str):
        """设置当前会话ID"""
        self._session_id = session_id
    
    async def register(self, websocket: "WebSocketServerProtocol"):
        """注册客户端连接"""
        async with self._lock:
            self._clients.add(websocket)
            logger.info(f"Client registered. Total clients: {len(self._clients)}")
    
    async def unregister(self, websocket: "WebSocketServerProtocol"):
        """注销客户端连接"""
        async with self._lock:
            self._clients.discard(websocket)
            logger.info(f"Client unregistered. Total clients: {len(self._clients)}")
    
    async def broadcast(self, message: WebSocketMessage):
        """广播消息到当前分析会话订阅的客户端。"""
        if not self._clients:
            logger.warning(
                "WS event dropped: session=%s event=%s agent=%s reason=no_clients",
                message.session_id,
                message.event.value,
                message.data.get("agent_id", ""),
            )
            return 0

        json_message = message.to_json()
        sent_count = 0
        async with self._lock:
            disconnected = set()
            for client in self._clients:
                try:
                    await client.send(json_message)
                    sent_count += 1
                except Exception as e:
                    logger.warning("Failed to send WS event: %s", e)
                    disconnected.add(client)
            self._clients -= disconnected

        logger.info(
            "WS event broadcast: session=%s event=%s agent=%s sent=%s failed=%s",
            message.session_id,
            message.event.value,
            message.data.get("agent_id", ""),
            sent_count,
            len(disconnected),
        )
        return sent_count
    
    # ========== Pipeline StateSync 接口实现 ==========
    
    async def on_session_start(self, tickers: list, date: str):
        """会话开始"""
        message = create_session_start_message(
            session_id=self._session_id,
            tickers=tickers,
            date=date,
        )
        await self.broadcast(message)
    
    async def on_session_end(self, success: bool = True, status: Optional[str] = None):
        """会话结束"""
        message = create_session_end_message(
            session_id=self._session_id,
            success=success,
            status=status,
        )
        await self.broadcast(message)
    
    async def on_agent_complete(self, agent_id: str, content: str):
        """广播 Agent 分析完成事件。"""
        logger.info(f"[on_agent_complete] Agent {agent_id} completed, content length: {len(content)}")
        
        message = create_agent_message(
            session_id=self._session_id,
            agent_id=agent_id,
            event=EventType.ANALYSIS_COMPLETE,
            content=content,
        )
        await self.broadcast(message)
        logger.info(f"[on_agent_complete] Broadcasted message for {agent_id}")
    
    async def on_agent_start(self, agent_id: str, phase: str = ""):
        """Agent开始分析"""
        message = create_agent_message(
            session_id=self._session_id,
            agent_id=agent_id,
            event=EventType.ANALYSIS_START,
            phase=phase,
        )
        await self.broadcast(message)
    
    async def on_agent_progress(
        self,
        agent_id: str,
        progress: float,
        content: str = "",
        phase: str = "",
    ):
        """Agent分析进度更新"""
        message = create_agent_message(
            session_id=self._session_id,
            agent_id=agent_id,
            event=EventType.ANALYSIS_PROGRESS,
            content=content,
            phase=phase,
            progress=progress,
        )
        await self.broadcast(message)
    
    async def on_agent_failed(self, agent_id: str, error: str, phase: str = ""):
        """广播 Agent 执行失败事件。"""
        message = create_agent_message(
            session_id=self._session_id,
            agent_id=agent_id,
            event=EventType.ANALYSIS_FAILED,
            content=error,
            phase=phase,
            progress=0,
        )
        await self.broadcast(message)

    async def on_conference_start(self, title: str, date: str):
        """会议开始"""
        message = create_conference_message(
            session_id=self._session_id,
            event=EventType.CONFERENCE_START,
            content=title,
        )
        await self.broadcast(message)
    
    async def on_conference_cycle_start(self, cycle: int, total_cycles: int):
        """会议轮次开始"""
        message = create_conference_message(
            session_id=self._session_id,
            event=EventType.ROUND_START,
            round_num=cycle,
            total_rounds=total_cycles,
        )
        await self.broadcast(message)
    
    async def on_conference_message(self, agent_id: str, content: str):
        """会议发言"""
        logger.info(f"[on_conference_message] Agent {agent_id} message, content length: {len(content)}")
        
        message = create_conference_message(
            session_id=self._session_id,
            event=EventType.MESSAGE,
            agent_id=agent_id,
            content=content,
        )
        await self.broadcast(message)
        logger.info(f"[on_conference_message] Broadcasted conference message for {agent_id}")

        # Persist to database
        if self._session_id:
            try:
                logger.info(f"[on_conference_message] Saving to database: session_id={self._session_id}, agent_id={agent_id}, phase=conference")
                db = await get_database()
                await db.save_agent_output(
                    session_id=self._session_id,
                    agent_id=agent_id,
                    agent_type="participant",
                    phase="conference",
                    content=content
                )
                logger.info(f"[on_conference_message] Successfully saved conference message for {agent_id}")
            except Exception as e:
                logger.error(f"[on_conference_message] Failed to save conference message: {e}", exc_info=True)
        else:
            logger.warning(f"[on_conference_message] No session_id, skipping database save")
    
    async def on_conference_cycle_end(self, cycle: int):
        """会议轮次结束"""
        message = create_conference_message(
            session_id=self._session_id,
            event=EventType.ROUND_END,
            round_num=cycle,
        )
        await self.broadcast(message)
    
    async def on_conference_end(self):
        """会议结束"""
        message = create_conference_message(
            session_id=self._session_id,
            event=EventType.CONFERENCE_END,
        )
        await self.broadcast(message)
    
    async def on_conference_summary(self, summary: str):
        """会议总结"""
        message = create_conference_message(
            session_id=self._session_id,
            event=EventType.SUMMARY,
            content=summary,
        )
        await self.broadcast(message)
    
    async def on_prediction_update(self, agent_id: str, predictions: list):
        """预测更新"""
        message = create_prediction_message(
            session_id=self._session_id,
            agent_id=agent_id,
            predictions=predictions,
        )
        await self.broadcast(message)
    
    async def on_report_generated(self, report: str):
        """报告生成"""
        message = create_report_message(
            session_id=self._session_id,
            report=report,
        )
        await self.broadcast(message)
