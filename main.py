# -*- coding: utf-8 -*-
# @Time: 2026/1/27 15:44
# @Author : aceplus
# @Desc : ==============================================
# Life is Short I Use Python!!!                      ===
# If this runs wrong,don't ask me,I don't know why.  ===
# If this runs right,thank god,and I don't know why. ===
# Maybe the answer,my friend,is blowing in the wind. ===
# ======================================================
# @Project : ZHANGXJ
# @FileName: main.py
# @Software: PyCharm

"""
AI Investor CLI入口

用于命令行直接运行分析（不启动服务器）
"""

import asyncio
import logging
import os
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from backend.agents import AnalystAgent, RiskAgent, PMAgent
from backend.config.constants import ANALYST_TYPES
from backend.config.env_config import get_env_float, get_env_int, get_env_list
from backend.core.pipeline import RatingPipeline
from backend.llm.models import get_agent_formatter, get_agent_model


load_dotenv()
logger = logging.getLogger(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)


def create_toolkit(analyst_type: str):
    """
    为分析师创建工具集

    Args:
        analyst_type: 分析师类型

    Returns:
        Toolkit 实例，包含该分析师类型对应的工具函数
    """
    from agentscope.tool import Toolkit

    if analyst_type == "fundamentals_analyst":
        from backend.agents.tools.fundamentals_tools import (
            analyze_profitability,
            analyze_growth,
            analyze_solvency,
            analyze_operating,
        )
        toolkit = Toolkit()
        toolkit.register_tool_function(analyze_profitability)
        toolkit.register_tool_function(analyze_growth)
        toolkit.register_tool_function(analyze_solvency)
        toolkit.register_tool_function(analyze_operating)
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
        toolkit.register_tool_function(comprehensive_valuation_analysis)
        toolkit.register_tool_function(dcf_valuation_analysis)
        toolkit.register_tool_function(residual_income_valuation_analysis)
        toolkit.register_tool_function(relative_valuation_analysis)
        toolkit.register_tool_function(get_wacc_breakdown)
        toolkit.register_tool_function(sotp_valuation_analysis)
        toolkit.register_tool_function(get_qualitative_insights)
        toolkit.register_tool_function(get_industry_competition)
        return toolkit

    return []


def create_long_term_memory(agent_name: str, config_name: str):
    """
    为Agent创建ReMe长记忆内存

    Requires DASHSCOPE_API_KEY env var
    """
    from agentscope.memory import ReMeTaskLongTermMemory
    from agentscope.model import DashScopeChatModel
    from agentscope.embedding import DashScopeTextEmbedding

    api_key = os.getenv("MEMORY_API_KEY")
    if not api_key:
        logger.warning("MEMORY_API_KEY not set, long-term memory disabled")
        return None

    memory_dir = str(Path(config_name) / "memory")

    return ReMeTaskLongTermMemory(
        agent_name=agent_name,
        user_name=agent_name,
        model=DashScopeChatModel(
            model_name=os.getenv("MEMORY_MODEL_NAME", "qwen3-max"),
            api_key=api_key,
            stream=False,
        ),
        embedding_model=DashScopeTextEmbedding(
            model_name=os.getenv(
                "MEMORY_EMBEDDING_MODEL",
                "text-embedding-v4",
            ),
            api_key=api_key,
            dimensions=1024,
        ),
        **{
            "vector_store.default.backend": "local",
            "vector_store.default.params.store_dir": memory_dir,
        },
    )


def create_agents(
    config_name: str,
    enable_long_term_memory: bool = False,
):
    """创建全部智能体"""
    analysts = []
    long_term_memories = []

    for analyst_type in ANALYST_TYPES:
        model = get_agent_model(analyst_type)
        formatter = get_agent_formatter(analyst_type)
        toolkit = create_toolkit(analyst_type)

        long_term_memory = None
        if enable_long_term_memory:
            long_term_memory = create_long_term_memory(
                analyst_type,
                config_name,
            )
            if long_term_memory:
                long_term_memories.append(long_term_memory)

        analyst = AnalystAgent(
            analyst_type=analyst_type,
            toolkit=toolkit,
            model=model,
            formatter=formatter,
            agent_id=analyst_type,
            config={"config_name": config_name},
            long_term_memory=long_term_memory,
        )
        analysts.append(analyst)

    # 创建风险管理Agent
    risk_long_term_memory = None
    if enable_long_term_memory:
        risk_long_term_memory = create_long_term_memory(
            "risk_manager",
            config_name,
        )
        if risk_long_term_memory:
            long_term_memories.append(risk_long_term_memory)

    risk_manager = RiskAgent(
        model=get_agent_model("risk_manager"),
        formatter=get_agent_formatter("risk_manager"),
        name="risk_manager",
        config={"config_name": config_name},
        long_term_memory=risk_long_term_memory,
    )

    # 创建投资组合管理Agent
    pm_long_term_memory = None
    if enable_long_term_memory:
        pm_long_term_memory = create_long_term_memory(
            "portfolio_manager",
            config_name,
        )
        if pm_long_term_memory:
            long_term_memories.append(pm_long_term_memory)

    portfolio_manager = PMAgent(
        name="portfolio_manager",
        model=get_agent_model("portfolio_manager"),
        formatter=get_agent_formatter("portfolio_manager"),
        config={"config_name": config_name},
        long_term_memory=pm_long_term_memory,
    )

    return analysts, risk_manager, portfolio_manager, long_term_memories


async def run_rating_cycle(
    pipeline: RatingPipeline,
    tickers: list,
    date: str,
    market_data: dict = None,
):
    """
    运行一个完整的评级周期
    
    Args:
        pipeline: 评级Pipeline实例
        tickers: 股票代码列表
        date: 日期
        market_data: 市场数据（可选）
    
    Returns:
        评级结果
    """
    result = await pipeline.run_cycle(
        tickers=tickers,
        date=date,
        market_data=market_data,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="AI Investor - 多Agent投资分析系统")
    parser.add_argument("--enable-memory", action="store_true", help="启用长记忆功能")
    parser.add_argument("--tickers", type=str, default="000001", help="股票代码，逗号分隔")
    parser.add_argument("--date", type=str, default=None, help="分析日期，格式：YYYY-MM-DD")
    parser.add_argument("--server", action="store_true", help="启动HTTP/WebSocket服务器")
    args = parser.parse_args()
    
    # 如果指定启动服务器，调用server模块
    if args.server:
        from backend.server import main as server_main
        server_main()
        return
    
    # 从环境变量获取配置
    config_name = os.getenv("CONFIG_NAME", "default")
    
    # 解析股票代码
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        tickers = get_env_list("TICKERS", ["000001"])
    
    # 解析日期
    date = args.date or datetime.now().strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info(f"AI Investor - 长期投资分析系统")
    logger.info("=" * 60)
    logger.info(f"配置名称: {config_name}")
    logger.info(f"长期记忆: {'启用' if args.enable_memory else '禁用'}")
    logger.info(f"分析标的: {tickers}")
    logger.info(f"分析日期: {date}")
    logger.info("开始创建智能体...")
    
    analysts, risk_manager, portfolio_manager, long_term_memories = create_agents(
        config_name=config_name,
        enable_long_term_memory=args.enable_memory,
    )
    
    logger.info(f"创建 {len(analysts)} 个分析师智能体")
    logger.info(f"风险管理器: {risk_manager.name}")
    logger.info(f"投资顾问: {portfolio_manager.name}")

    # 创建Pipeline
    pipeline = RatingPipeline(
        analysts=analysts,
        risk_manager=risk_manager,
        portfolio_manager=portfolio_manager,
        max_comm_cycles=get_env_int("MAX_COMM_CYCLES", 2),
    )

    # 运行评级流程
    logger.info("=" * 60)
    logger.info("开始运行投资分析流程...")
    logger.info("=" * 60)
    
    result = asyncio.run(run_rating_cycle(
        pipeline=pipeline,
        tickers=tickers,
        date=date,
        market_data=None,  # TODO: 集成实际数据源
    ))

    # 输出结果
    logger.info("=" * 60)
    logger.info("投资分析流程完成")
    logger.info("=" * 60)
    
    if result:
        # 输出评级报告
        rating_report = result.get("rating_report", "")
        if rating_report:
            print("\n")
            print(rating_report)
        
        # 输出投资建议摘要
        recommendations = result.get("investment_recommendations", {})
        if recommendations:
            content = recommendations.get("content", "")
            if content:
                print("\n" + "=" * 60)
                print("投资建议详情:")
                print("=" * 60)
                if isinstance(content, str):
                    print(content)
                else:
                    print(str(content))


if __name__ == "__main__":
    main()
