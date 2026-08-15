# -*- coding: utf-8 -*-
"""
消息格式定义

统一的WebSocket消息格式，支持多种事件类型
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import json
import uuid


class MessageType(str, Enum):
    """消息类型"""
    SYSTEM = "system"
    AGENT = "agent"
    CONFERENCE = "conference"
    PREDICTION = "prediction"
    REPORT = "report"
    ERROR = "error"


class EventType(str, Enum):
    """事件类型"""
    # System events
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    CANCELLATION_REQUESTED = "cancellation_requested"
    PING = "ping"
    PONG = "pong"
    
    # Agent events
    ANALYSIS_START = "analysis_start"
    ANALYSIS_PROGRESS = "analysis_progress"
    ANALYSIS_COMPLETE = "analysis_complete"
    ANALYSIS_FAILED = "analysis_failed"
    
    # Conference events
    CONFERENCE_START = "conference_start"
    ROUND_START = "round_start"
    MESSAGE = "message"
    ROUND_END = "round_end"
    CONFERENCE_END = "conference_end"
    SUMMARY = "summary"
    
    # Prediction events
    PREDICTION_UPDATE = "prediction_update"
    
    # Report events
    REPORT_GENERATED = "report_generated"
    
    # Error events
    ERROR = "error"


def _utc_timestamp() -> str:
    """Return an ISO 8601 timestamp unambiguous to WebSocket clients."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WebSocketMessage:
    """WebSocket消息格式"""
    type: MessageType
    event: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    timestamp: str = field(default_factory=_utc_timestamp)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "event": self.event.value if isinstance(self.event, Enum) else self.event,
            "data": self.data,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }
    
    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """从JSON字符串解析"""
        data = json.loads(json_str)
        return cls(
            type=MessageType(data.get("type", "system")),
            event=EventType(data.get("event", "ping")),
            data=data.get("data", {}),
            session_id=data.get("session_id"),
            timestamp=data.get("timestamp", _utc_timestamp()),
            message_id=data.get("message_id", str(uuid.uuid4())),
        )


# 快捷创建消息的工厂函数
def create_session_start_message(session_id: str, tickers: list, date: str) -> WebSocketMessage:
    """创建会话开始消息"""
    return WebSocketMessage(
        type=MessageType.SYSTEM,
        event=EventType.SESSION_START,
        session_id=session_id,
        data={
            "tickers": tickers,
            "date": date,
        }
    )


def create_session_end_message(
    session_id: str,
    success: bool = True,
    status: Optional[str] = None,
) -> WebSocketMessage:
    """创建会话结束消息"""
    return WebSocketMessage(
        type=MessageType.SYSTEM,
        event=EventType.SESSION_END,
        session_id=session_id,
        data={
            "success": success,
            "status": status or ("completed" if success else "failed"),
        }
    )


def create_cancellation_requested_message(session_id: str) -> WebSocketMessage:
    """创建分析取消已受理消息。"""
    return WebSocketMessage(
        type=MessageType.SYSTEM,
        event=EventType.CANCELLATION_REQUESTED,
        session_id=session_id,
        data={"status": "cancelling"},
    )


def create_agent_message(
    session_id: str,
    agent_id: str,
    event: EventType,
    content: str = "",
    phase: str = "",
    progress: float = 0.0,
) -> WebSocketMessage:
    """创建Agent消息"""
    return WebSocketMessage(
        type=MessageType.AGENT,
        event=event,
        session_id=session_id,
        data={
            "agent_id": agent_id,
            "content": content,
            "phase": phase,
            "progress": progress,
        }
    )


def create_conference_message(
    session_id: str,
    event: EventType,
    agent_id: str = "",
    content: str = "",
    round_num: int = 0,
    total_rounds: int = 0,
) -> WebSocketMessage:
    """创建会议消息"""
    return WebSocketMessage(
        type=MessageType.CONFERENCE,
        event=event,
        session_id=session_id,
        data={
            "agent_id": agent_id,
            "content": content,
            "round": round_num,
            "total_rounds": total_rounds,
        }
    )


def create_prediction_message(
    session_id: str,
    agent_id: str,
    predictions: list,
) -> WebSocketMessage:
    """创建预测消息"""
    return WebSocketMessage(
        type=MessageType.PREDICTION,
        event=EventType.PREDICTION_UPDATE,
        session_id=session_id,
        data={
            "agent_id": agent_id,
            "predictions": predictions,
        }
    )


def create_report_message(session_id: str, report: str) -> WebSocketMessage:
    """创建报告消息"""
    return WebSocketMessage(
        type=MessageType.REPORT,
        event=EventType.REPORT_GENERATED,
        session_id=session_id,
        data={"report": report}
    )


def create_error_message(
    session_id: str,
    error: str,
    details: str = "",
    command: Optional[str] = None,
) -> WebSocketMessage:
    """创建错误消息"""
    data = {
        "error": error,
        "details": details,
    }
    if command:
        data["command"] = command

    return WebSocketMessage(
        type=MessageType.ERROR,
        event=EventType.ERROR,
        session_id=session_id,
        data=data,
    )
