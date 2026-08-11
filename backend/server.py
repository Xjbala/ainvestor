# -*- coding: utf-8 -*-
"""
AI Investor 后端服务入口

整合FastAPI和WebSocket服务，提供完整的后端能力
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router
from backend.api.auth import router as auth_router
from backend.api.users import router as users_router
from backend.api.crawler import router as crawler_router
from backend.api.analysis import router as analysis_router
from backend.api.valuation import router as valuation_router
from backend.api.companies import router as companies_router
from backend.api.exchanges import router as exchanges_router
from backend.api.segments import router as segments_router
from backend.persistence.compat import get_database, close_database
from backend.websocket.gateway import WebSocketGateway
from backend.websocket.state_sync import WebSocketStateSync
from backend.agents.tool_progress import with_tool_progress

load_dotenv()

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# 全局变量
ws_gateway: WebSocketGateway = None


def _create_analyst_toolkit(
    analyst_type: str,
    *,
    report_tool_progress: bool = False,
):
    """为分析师创建工具集"""
    from agentscope.tool import Toolkit

    if analyst_type == "fundamentals_analyst":
        from backend.agents.tools.fundamentals_tools import (
            analyze_profitability,
            analyze_growth,
            analyze_solvency,
            analyze_operating,
        )
        toolkit = Toolkit()
        for tool_function in (
            analyze_profitability,
            analyze_growth,
            analyze_solvency,
            analyze_operating,
        ):
            toolkit.register_tool_function(
                with_tool_progress(tool_function) if report_tool_progress else tool_function,
            )
        return toolkit

    elif analyst_type == "valuation_analyst":
        from backend.agents.tools.valuation_tools import (
            comprehensive_valuation_analysis,
            dcf_valuation_analysis,
            residual_income_valuation_analysis,
            relative_valuation_analysis,
            get_wacc_breakdown,
            sotp_valuation_analysis,
        )
        from backend.agents.tools.qualitative_tools import (
            get_qualitative_insights,
            get_industry_competition,
        )
        toolkit = Toolkit()
        for tool_function in (
            comprehensive_valuation_analysis,
            dcf_valuation_analysis,
            residual_income_valuation_analysis,
            relative_valuation_analysis,
            get_wacc_breakdown,
            sotp_valuation_analysis,
            get_qualitative_insights,
            get_industry_competition,
        ):
            toolkit.register_tool_function(
                with_tool_progress(tool_function) if report_tool_progress else tool_function,
            )
        return toolkit

    return []


async def run_analysis(
    tickers: List[str],
    date: str,
    session_id: str,
    session_sync: WebSocketStateSync,
):
    """
    运行投资分析流程
    
    这是WebSocket网关的分析处理器，当收到分析请求时被调用
    """
    from backend.agents import AnalystAgent, RiskAgent, PMAgent
    from backend.config.constants import ANALYST_TYPES
    from backend.config.env_config import get_env_int
    from backend.core.pipeline import RatingPipeline
    from backend.llm.models import get_agent_formatter, get_agent_model
    
    logger.info(f"Starting analysis: session={session_id}, tickers={tickers}, date={date}")
    
    # 获取数据库
    db = await get_database()
    
    # 创建会话记录 (使用网关传入的session_id以确保一致性)
    session = await db.create_session(tickers=tickers, date=date, session_id=session_id)
    await db.update_session_status(session.id, "running")
    
    try:
        # 创建分析师
        analysts = []
        for analyst_type in ANALYST_TYPES:
            model = get_agent_model(analyst_type)
            formatter = get_agent_formatter(analyst_type)
            toolkit = _create_analyst_toolkit(
                analyst_type,
                report_tool_progress=True,
            )
            analyst = AnalystAgent(
                analyst_type=analyst_type,
                toolkit=toolkit,
                model=model,
                formatter=formatter,
                agent_id=analyst_type,
                config={"config_name": "default"},
            )
            analysts.append(analyst)
        
        # 创建风险管理器
        risk_manager = RiskAgent(
            model=get_agent_model("risk_manager"),
            formatter=get_agent_formatter("risk_manager"),
            name="risk_manager",
            config={"config_name": "default"},
        )
        
        # 创建投资组合管理器
        portfolio_manager = PMAgent(
            name="portfolio_manager",
            model=get_agent_model("portfolio_manager"),
            formatter=get_agent_formatter("portfolio_manager"),
            config={"config_name": "default"},
        )
        
        # 创建Pipeline
        pipeline = RatingPipeline(
            analysts=analysts,
            risk_manager=risk_manager,
            portfolio_manager=portfolio_manager,
            state_sync=session_sync,
            max_comm_cycles=get_env_int("MAX_COMM_CYCLES", 2),
        )
        
        # 确保 pipeline 持有与网关一致的 session_id
        pipeline._session_id = session.id
        session_sync.set_session_id(session.id)

        # 运行分析
        result = await pipeline.run_cycle(
            tickers=tickers,
            date=date,
            market_data=None,
        )

        # 保存并广播报告（任一步失败不阻断会话完成状态）
        if result and result.get("rating_report"):
            try:
                await db.save_report(
                    session_id=session.id,
                    report_content=result["rating_report"],
                    recommendations=result.get("investment_recommendations"),
                )
            except Exception as e:
                logger.error(f"Failed to save report for session={session.id}: {e}", exc_info=True)

            try:
                await session_sync.on_report_generated(result["rating_report"])
            except Exception as e:
                logger.error(f"Failed to broadcast report for session={session.id}: {e}", exc_info=True)

        # 更新会话状态
        await db.update_session_status(session.id, "completed")
        logger.info(f"Analysis completed: session={session.id}")

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        try:
            await db.update_session_status(session.id, "failed")
        except Exception:
            pass
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global ws_gateway
    
    # 启动时
    logger.info("Starting AI Investor backend...")
    
    # 初始化数据库
    await get_database()
    
    # 创建WebSocket网关
    ws_gateway = WebSocketGateway(
        host="0.0.0.0",
        port=int(os.getenv("WS_PORT", "8765")),
    )
    ws_gateway.set_analysis_handler(run_analysis)
    
    # 在后台启动WebSocket服务器
    asyncio.create_task(ws_gateway.start())
    logger.info("WebSocket gateway started")
    
    yield
    
    # 关闭时
    logger.info("Shutting down AI Investor backend...")
    if ws_gateway:
        await ws_gateway.stop()
    await close_database()


# 创建FastAPI应用
app = FastAPI(
    title="AI Investor API",
    description="AI投资分析系统后端API",
    version="0.1.0",
    lifespan=lifespan,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有源
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(crawler_router)
app.include_router(analysis_router)
app.include_router(valuation_router)
app.include_router(companies_router)
app.include_router(exchanges_router)
app.include_router(segments_router)


@app.get("/")
async def root():
    """根路由"""
    return {
        "name": "AI Investor API",
        "version": "0.1.0",
        "docs": "/docs",
    }


def main():
    """主入口"""
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"WebSocket port: {os.getenv('WS_PORT', '8765')}")
    
    uvicorn.run(
        app,  # 直接传入app实例而非字符串
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
