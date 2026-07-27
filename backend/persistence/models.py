# -*- coding: utf-8 -*-
"""
状态持久化 - 数据库模型

使用SQLite存储分析会话和结果
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AnalysisSession:
    """分析会话"""
    id: str
    tickers: str  # JSON array
    date: str
    status: str  # pending, running, completed, failed
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    mode: str = "ai"  # ai or expert


@dataclass
class AgentOutput:
    """Agent输出"""
    id: str
    session_id: str
    agent_id: str
    agent_type: str  # analyst, risk_manager, portfolio_manager
    phase: str  # analysis, conference, prediction
    content: str
    created_at: datetime


@dataclass
class RatingReport:
    """评级报告"""
    id: str
    session_id: str
    report_content: str
    recommendations: str  # JSON
    created_at: datetime
