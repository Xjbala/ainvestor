# -*- coding: utf-8 -*-
"""
REST API路由

提供HTTP接口用于查询历史会话和报告
"""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..persistence.compat import get_database

router = APIRouter(prefix="/api", tags=["api"])


# ========== 请求/响应模型 ==========

class StartAnalysisRequest(BaseModel):
    """启动分析请求"""
    tickers: List[str]
    date: Optional[str] = None


class SessionResponse(BaseModel):
    """会话响应"""
    id: str
    tickers: List[str]
    date: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    mode: Optional[str] = "ai"


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    tickers: List[str]
    date: str
    status: str = 'running'
    mode: Optional[str] = 'ai'


class AgentOutputResponse(BaseModel):
    """Agent输出响应"""
    id: str
    agent_id: str
    agent_type: str
    phase: str
    content: str
    created_at: str


class ReportResponse(BaseModel):
    """报告响应"""
    id: str
    session_id: str
    report_content: str
    recommendations: Optional[dict] = None
    created_at: str


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str


# ========== 路由 ==========

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """创建新的分析会话"""
    db = await get_database()
    session = await db.create_session(
        tickers=request.tickers,
        date=request.date,
        status=request.status,
        mode=request.mode or "ai"
    )
    
    return SessionResponse(
        id=session.id,
        tickers=json.loads(session.tickers),
        date=session.date,
        status=session.status,
        created_at=session.created_at.isoformat(),
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
    )


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(limit: int = 10):
    """获取最近的分析会话"""
    db = await get_database()
    sessions = await db.get_recent_sessions(limit=limit)
    
    return [
        SessionResponse(
            id=s.id,
            tickers=json.loads(s.tickers),
            date=s.date,
            status=s.status,
            created_at=s.created_at.isoformat(),
            completed_at=s.completed_at.isoformat() if s.completed_at else None,
            mode=getattr(s, 'mode', 'ai')
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """获取指定会话"""
    db = await get_database()
    session = await db.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        id=session.id,
        tickers=json.loads(session.tickers),
        date=session.date,
        status=session.status,
        created_at=session.created_at.isoformat(),
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
        mode=getattr(session, 'mode', 'ai')
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """删除已结束的分析会话、Agent 输出和评级报告。"""
    db = await get_database()
    try:
        deleted = await db.delete_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}/outputs", response_model=List[AgentOutputResponse])
async def get_session_outputs(session_id: str):
    """获取会话的Agent输出"""
    db = await get_database()
    outputs = await db.get_session_outputs(session_id)
    
    return [
        AgentOutputResponse(
            id=o.id,
            agent_id=o.agent_id,
            agent_type=o.agent_type,
            phase=o.phase,
            content=o.content,
            created_at=o.created_at.isoformat(),
        )
        for o in outputs
    ]


@router.get("/sessions/{session_id}/report", response_model=ReportResponse)
async def get_session_report(session_id: str):
    """获取会话的评级报告"""
    db = await get_database()
    report = await db.get_report(session_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    recommendations = None
    if report.recommendations:
        try:
            recommendations = json.loads(report.recommendations)
        except json.JSONDecodeError:
            pass
    
    return ReportResponse(
        id=report.id,
        session_id=report.session_id,
        report_content=report.report_content,
        recommendations=recommendations,
        created_at=report.created_at.isoformat(),
    )
