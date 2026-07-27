# -*- coding: utf-8 -*-
"""
评级 Pipeline - 多Agent协作价值投资分析流程

实现从财务分析到投资建议生成的完整流程，包含记忆清理、
分析师评估、风险控制、会议讨论、最终预测和投资建议生成。
"""

import json
import logging
import os
import re
import asyncio
import random
from typing import Any, Dict, List, Optional, Callable, Awaitable

from agentscope.message import Msg
from agentscope.pipeline import MsgHub

from ..persistence.compat import get_database

logger = logging.getLogger(__name__)


def _log(msg: str):
    """Log to dashboard if available, otherwise to logger"""
    logger.info(msg)


async def _retry_with_backoff(
    coro_func: Callable[[], Awaitable[Any]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
) -> Any:
    """
    带指数退避的异步重试装饰器

    用于包装 LLM 调用等可能因网络/限流失败的异步操作。

    Args:
        coro_func: 要执行的异步函数
        max_retries: 最大重试次数
        base_delay: 基础延迟秒数
        max_delay: 最大延迟秒数
        retryable_exceptions: 可重试的异常类型

    Returns:
        函数返回值

    Raises:
        最后一次重试失败时的异常
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except retryable_exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(
                    f"操作失败，已达最大重试次数 {max_retries}: {type(e).__name__}: {e}"
                )
                raise

            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
            logger.warning(
                f"操作失败 ({type(e).__name__}: {e}), "
                f"第 {attempt + 1}/{max_retries} 次重试, "
                f"{delay:.1f}秒后重试..."
            )
            await asyncio.sleep(delay)

    # 理论上不会到达这里，但为了类型检查完整性
    raise last_exception


class StateSync:
    """
    状态同步器（可选）
    
    用于在Pipeline执行过程中实时同步状态到外部系统（如Dashboard）
    """
    
    async def on_agent_complete(self, agent_id: str, content: str):
        """Agent完成时的回调"""
        _log(f"Agent {agent_id} completed")
    
    async def on_conference_start(self, title: str, date: str):
        """会议开始时的回调"""
        _log(f"Conference started: {title}")
    
    async def on_conference_cycle_start(self, cycle: int, total_cycles: int):
        """会议轮次开始时的回调"""
        _log(f"Conference cycle {cycle}/{total_cycles} started")
    
    async def on_conference_message(self, agent_id: str, content: str):
        """会议消息的回调"""
        _log(f"Conference message from {agent_id}")
    
    async def on_conference_cycle_end(self, cycle: int):
        """会议轮次结束时的回调"""
        _log(f"Conference cycle {cycle} ended")
    
    async def on_conference_end(self):
        """会议结束时的回调"""
        _log("Conference ended")


class RatingPipeline:
    """
    评级Pipeline - 长期投资分析与估值评级流程

    Flow:
    1. Clear agent short-term memory (避免跨日上下文污染)
    2. Analysts analyze stocks (分析师评估)
    3. Risk Manager provides risk assessment (风险评估)
    4. Conference discussion cycles (会议讨论，多轮)
    5. Analysts generate final predictions (生成结构化预测)
    6. PM provides investment recommendations (生成投资建议)
    7. Generate rating report (生成评级报告)
    8. Reflection phase - record to long-term memory (生成记忆)

    Real-time updates via StateSync after each agent completes.
    """

    def __init__(
        self,
        analysts: List[Any],
        risk_manager: Any,
        portfolio_manager: Any,
        state_sync: Optional["StateSync"] = None,
        max_comm_cycles: Optional[int] = None,
    ):
        self.analysts = analysts
        self.risk_manager = risk_manager
        self.pm = portfolio_manager
        self.state_sync = state_sync
        self.max_comm_cycles = max_comm_cycles or int(
            os.getenv("MAX_COMM_CYCLES", "2"),
        )
        self.conference_summary = None
        self._session_id: Optional[str] = None

    async def _persist_agent_output(
        self,
        agent_id: str,
        agent_type: str,
        phase: str,
        content: str,
    ) -> None:
        """持久化 Agent 输出到数据库"""
        # 无 state_sync 时（如 CLI）不落库；有 state_sync 时优先用其 session_id
        session_id = self._session_id or (
            getattr(self.state_sync, "_session_id", None) if self.state_sync else None
        )
        if not session_id:
            return
        try:
            # get_database 是 async 工厂，必须 await
            db = await get_database()
            # 将扩展 phase 映射到 ORM 枚举可接受的值
            phase_map = {
                "analysis": "analysis",
                "conference": "conference",
                "prediction": "prediction",
                "risk_assessment": "analysis",
                "investment_recommendation": "prediction",
            }
            persist_phase = phase_map.get(phase, "analysis")
            await db.save_agent_output(
                session_id=session_id,
                agent_id=agent_id,
                agent_type=agent_type,
                phase=persist_phase,
                content=content if isinstance(content, str) else str(content or ""),
            )
        except Exception as e:
            logger.warning(f"Failed to persist agent output [{agent_id}/{phase}]: {e}")

    async def run_cycle(
        self,
        tickers: List[str],
        date: str,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        运行一个完整的评级流程

        Args:
            tickers: List of stock tickers
            date: Analysis date (YYYY-MM-DD)
            market_data: Optional market data for analysis

        Returns:
            完整的评级结果字典
        """
        _log(f"Starting rating cycle {date} - {len(tickers)} tickers")

        # Reset PM decisions for this new analysis cycle
        self.pm.reset_decisions()

        # Store session ID for persistence
        if self.state_sync:
            self._session_id = getattr(self.state_sync, '_session_id', None)

        # Phase 0: Clear short-term memory to avoid cross-day context pollution
        _log("Phase 0: Clearing memory")
        await self._clear_all_agent_memory()

        participants = self.analysts + [self.risk_manager, self.pm]

        # Single MsgHub for entire cycle - no nesting
        async with MsgHub(
            participants=participants,
            announcement=Msg(
                "system",
                f"Starting investment analysis cycle for {date}. Tickers: {', '.join(tickers)}",
                "system",
            ),
        ):
            # Phase 1: Analysts analyze stocks (分析师评估)
            _log("Phase 1: Analyst analysis")
            analyst_results = await self._run_analysts_with_sync(tickers, date, market_data)

            # Phase 2: Risk Manager provides assessment (风险评估)
            _log("Phase 2: Risk assessment")
            risk_assessment = await self._run_risk_manager_with_sync(
                tickers,
                date,
                market_data,
                analyst_results=analyst_results,
            )

            # Phase 3: Conference discussion - multiple rounds (会议讨论，多轮)
            _log("Phase 3: Conference discussion")
            conference_summary = await self._run_conference_cycles(
                tickers=tickers,
                date=date,
                market_data=market_data,
                analyst_results=analyst_results,
                risk_assessment=risk_assessment,
            )
            self.conference_summary = conference_summary

            # Phase 4: Analysts generate final structured predictions (生成结构化预测)
            _log("Phase 4: Analysts generate final structured predictions")
            final_predictions = await self._collect_final_predictions(
                tickers,
                date,
            )

            # Phase 5: PM provides investment recommendations (生成投资建议)
            _log("Phase 5: PM generates investment recommendations")
            investment_recommendations = await self._run_pm_recommendations(
                tickers,
                date,
                analyst_results,
                risk_assessment,
                final_predictions,
            )

        # Phase 6: Generate rating report (生成评级报告)
        _log("Phase 6: Generating rating report")
        rating_report = self._generate_rating_report(
            date=date,
            tickers=tickers,
            analyst_results=analyst_results,
            risk_assessment=risk_assessment,
            final_predictions=final_predictions,
            investment_recommendations=investment_recommendations,
            conference_summary=conference_summary,
        )

        # Phase 7: Reflection - record to long-term memory (生成记忆)
        _log("Phase 7: Reflection and memory recording")
        await self._run_reflection(
            date=date,
            analyst_results=analyst_results,
            risk_assessment=risk_assessment,
            investment_recommendations=investment_recommendations,
            conference_summary=conference_summary,
        )

        _log(f"Rating cycle complete: {date}")

        return {
            "date": date,
            "tickers": tickers,
            "analyst_results": analyst_results,
            "risk_assessment": risk_assessment,
            "final_predictions": final_predictions,
            "conference_summary": conference_summary,
            "investment_recommendations": investment_recommendations,
            "rating_report": rating_report,
        }

    def _generate_rating_report(
        self,
        date: str,
        tickers: List[str],
        analyst_results: List[Dict[str, Any]],
        risk_assessment: Dict[str, Any],
        final_predictions: List[Dict[str, Any]],
        investment_recommendations: Dict[str, Any],
        conference_summary: Optional[str],
    ) -> str:
        """生成评级报告（纯文本，剥离 thinking / tool 块）"""
        def _clean(content: Any, limit: Optional[int] = None) -> str:
            text = self._extract_text_content(content)
            text = text.strip()
            if limit is not None and len(text) > limit:
                return text[:limit] + "..."
            return text

        # 从 PM JSON 抽取结构化决策，写入报告头部便于前端解析
        decision_block = self._format_decision_summary(investment_recommendations, tickers)

        lines = [
            "# 股票投资评级报告",
            f"**分析日期**: {date}",
            f"**分析标的**: {', '.join(tickers)}",
            "",
            decision_block,
            "",
            "---",
            "",
            "## 一、分析师评估摘要",
            "",
        ]

        for result in analyst_results:
            agent = result.get("agent", "Unknown")
            summary = _clean(result.get("content", ""), limit=800)
            lines.append(f"### {agent}")
            lines.append(summary or "（无有效文本输出）")
            lines.append("")

        risk_text = _clean(risk_assessment.get("content", "无风险评估信息"))
        lines.extend([
            "---",
            "",
            "## 二、风险评估",
            "",
            risk_text or "无风险评估信息",
            "",
            "---",
            "",
            "## 三、投资建议",
            "",
        ])

        rec_text = _clean(investment_recommendations.get("content", ""))
        lines.append(rec_text or "（无投资建议文本）")

        if conference_summary:
            conf_text = _clean(conference_summary)
            lines.extend([
                "",
                "---",
                "",
                "## 四、分析师会议讨论要点",
                "",
                conf_text,
            ])

        lines.extend([
            "",
            "---",
            "",
            "## 五、分析师预测汇总",
            "",
        ])

        for prediction in final_predictions:
            agent = prediction.get("agent", "Unknown")
            predictions_data = prediction.get("predictions", [])
            lines.append(f"### {agent}")
            for pred in predictions_data:
                ticker = pred.get("ticker", "")
                direction = pred.get("direction", "neutral")
                confidence = pred.get("confidence", 0.5)
                rating = self._direction_to_rating(direction)
                lines.append(f"- **{ticker}**: {rating} (置信度: {confidence*100:.0f}%)")
            lines.append("")

        lines.extend([
            "---",
            "",
            "*本报告由AI投资分析系统自动生成，仅供参考，不构成投资建议。*",
        ])

        return "\n".join(lines)

    def _format_decision_summary(
        self,
        investment_recommendations: Dict[str, Any],
        tickers: List[str],
    ) -> str:
        """从 PM 输出解析结构化评级，生成前端可解析的摘要块。"""
        text = self._extract_text_content(investment_recommendations.get("content", ""))
        rating = None
        target_price = None
        target_range = None
        holding = None

        # 1) JSON recommendations 块
        try:
            m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
            raw = m.group(1) if m else None
            if not raw:
                m2 = re.search(
                    r"(\{\s*\"recommendations\"\s*:\s*\[[\s\S]*?\]\s*\})",
                    text,
                )
                raw = m2.group(1) if m2 else None
            if raw:
                data = json.loads(raw)
                recs = data.get("recommendations") or []
                if recs:
                    first = recs[0] if isinstance(recs[0], dict) else {}
                    rating = first.get("rating")
                    target_price = first.get("target_price")
                    target_range = first.get("target_price_range")
                    holding = first.get("holding_period")
        except Exception:
            pass

        # 2) 中文标签回退
        if not rating:
            for pat in (
                r"【投资评级】[：:]\s*([^\n]+)",
                r"投资评级[：:]\s*([^\n]+)",
                r"\"rating\"\s*:\s*\"([^\"]+)\"",
            ):
                m = re.search(pat, text)
                if m:
                    rating = m.group(1).strip()
                    break

        if target_price in (None, "", "null") and not target_range:
            m = re.search(r"目标价位区间[：:]\s*([^\n]+)", text)
            if m:
                target_range = m.group(1).strip()
            m = re.search(r"目标价[位]?[：:]\s*([^\n]+)", text)
            if m and not target_range:
                target_price = m.group(1).strip()

        # 归一化评级
        rating_norm = "中性"
        if rating:
            if any(k in str(rating) for k in ("强烈推荐", "强烈买入")):
                rating_norm = "强烈推荐"
            elif any(k in str(rating) for k in ("推荐", "买入", "增持")):
                rating_norm = "推荐"
            elif any(k in str(rating) for k in ("回避", "卖出")):
                rating_norm = "回避"
            elif any(k in str(rating) for k in ("谨慎", "减持")):
                rating_norm = "谨慎"
            elif any(k in str(rating) for k in ("中性", "持有", "观望")):
                rating_norm = "中性"
            else:
                rating_norm = str(rating).strip()

        # 目标价展示
        if target_price not in (None, "", "null"):
            try:
                tp_disp = f"¥{float(target_price):.2f}"
            except (TypeError, ValueError):
                tp_disp = str(target_price)
        elif target_range not in (None, "", "null", "无有效目标价", "无", "不适用"):
            tp_disp = str(target_range)
        else:
            tp_disp = "—"

        ticker_str = ", ".join(tickers) if tickers else "—"
        return "\n".join([
            "## 决策摘要",
            f"**投资评级**: {rating_norm}",
            f"**目标价位**: {tp_disp}",
            f"**持有期限**: {holding or '—'}",
            f"**标的**: {ticker_str}",
        ])

    def _direction_to_rating(self, direction: str) -> str:
        """将方向转换为评级"""
        mapping = {
            "up": "买入 📈",
            "down": "卖出 📉",
            "neutral": "持有 ➡️",
        }
        return mapping.get(direction.lower(), "持有 ➡️")

    async def _clear_all_agent_memory(self):
        """Clear short-term memory for all agents"""
        for analyst in self.analysts:
            if hasattr(analyst, 'memory') and analyst.memory:
                await analyst.memory.clear()

        if hasattr(self.risk_manager, 'memory') and self.risk_manager.memory:
            await self.risk_manager.memory.clear()
        
        if hasattr(self.pm, 'memory') and self.pm.memory:
            await self.pm.memory.clear()

    async def _run_reflection(
        self,
        date: str,
        analyst_results: List[Dict[str, Any]],
        risk_assessment: Dict[str, Any],
        investment_recommendations: Dict[str, Any],
        conference_summary: Optional[str],
    ):
        """
        运行反思阶段，将经验记录到长期记忆
        """
        # 构建反思消息
        reflection_content = f"""
日期: {date}

今日分析回顾：

分析师评估数量: {len(analyst_results)}

风险评估要点:
{risk_assessment.get("content", "无")[:300]}

投资建议要点:
{investment_recommendations.get("content", "无")[:300]}

请回顾今天的分析过程，总结关键学习点和改进建议。
"""

        reflection_msg = Msg(
            name="system",
            content=reflection_content,
            role="user",
        )

        # 分析师反思
        for analyst in self.analysts:
            if hasattr(analyst, 'long_term_memory') and analyst.long_term_memory:
                try:
                    await analyst.reply(reflection_msg)
                    _log(f"Reflection recorded for {analyst.name}")
                except Exception as e:
                    logger.warning(f"Failed to record reflection for {analyst.name}: {e}")

        # 风险管理器反思
        if hasattr(self.risk_manager, 'long_term_memory') and self.risk_manager.long_term_memory:
            try:
                await self.risk_manager.reply(reflection_msg)
                _log("Reflection recorded for risk_manager")
            except Exception as e:
                logger.warning(f"Failed to record reflection for risk_manager: {e}")

        # PM反思
        if hasattr(self.pm, 'long_term_memory') and self.pm.long_term_memory:
            try:
                await self.pm.reply(reflection_msg)
                _log("Reflection recorded for portfolio_manager")
            except Exception as e:
                logger.warning(f"Failed to record reflection for portfolio_manager: {e}")

    async def _sync_memory_if_retrieved(self, agent: Any):
        """Retrieve and sync long-term memory if enabled"""
        if hasattr(agent, 'long_term_memory') and agent.long_term_memory:
            try:
                # 触发记忆检索，确保 Agent 从长期记忆中获取相关信息
                await agent.long_term_memory.retrieve(agent.name)
                logger.debug(f"Memory retrieved for agent: {agent.name}")
            except Exception as e:
                logger.warning(f"Memory retrieval failed for {agent.name}: {e}")

    async def _run_conference_cycles(
        self,
        tickers: List[str],
        date: str,
        market_data: Optional[Dict[str, Any]],
        analyst_results: List[Dict[str, Any]],
        risk_assessment: Dict[str, Any],
    ) -> Optional[str]:
        """
        Run conference discussion cycles (within existing MsgHub context)

        Returns:
            Conference summary string generated by PM
        """
        if self.max_comm_cycles <= 0:
            _log("Phase 3: Conference discussion - skipped (disabled)")
            return None

        conference_title = f"Investment Analysis Discussion - {date}"

        if self.state_sync:
            await self.state_sync.on_conference_start(
                title=conference_title,
                date=date,
            )

        # Run discussion cycles
        for cycle in range(self.max_comm_cycles):
            _log(f"Phase 3: Conference discussion - Round {cycle + 1}/{self.max_comm_cycles}")

            if self.state_sync:
                await self.state_sync.on_conference_cycle_start(
                    cycle=cycle + 1,
                    total_cycles=self.max_comm_cycles,
                )

            # PM sets agenda or asks questions
            pm_prompt = self._build_pm_discussion_prompt(
                cycle=cycle,
                tickers=tickers,
                date=date,
                analyst_results=analyst_results,
                risk_assessment=risk_assessment,
            )

            pm_msg = Msg(name="system", content=pm_prompt, role="user")
            pm_response = await _retry_with_backoff(
                lambda: self.pm.reply(pm_msg),
                max_retries=3,
            )

            if self.state_sync:
                pm_content = self._extract_text_content(pm_response.content)
                await self.state_sync.on_conference_message(
                    agent_id="portfolio_manager",
                    content=pm_content,
                )

            # Analysts share perspectives
            for analyst in self.analysts:
                analyst_prompt = self._build_analyst_discussion_prompt(
                    cycle=cycle,
                    tickers=tickers,
                    date=date,
                    analyst_results=analyst_results,
                    risk_assessment=risk_assessment,
                )

                analyst_msg = Msg(
                    name="system",
                    content=analyst_prompt,
                    role="user",
                )
                analyst_response = await _retry_with_backoff(
                    lambda a=analyst, m=analyst_msg: a.reply(m),
                    max_retries=3,
                )

                if self.state_sync:
                    analyst_content = self._extract_text_content(
                        analyst_response.content,
                    )
                    await self.state_sync.on_conference_message(
                        agent_id=analyst.name,
                        content=analyst_content,
                    )

            if self.state_sync:
                await self.state_sync.on_conference_cycle_end(cycle=cycle + 1)

        # Generate conference summary by PM
        _log("Phase 3: Conference discussion - Generating summary")
        summary_prompt = (
            f"投资分析会议 {date} 已结束。"
            f"作为投资组合经理，请提供一份简洁的会议摘要，包括："
            f"1. 关于 {', '.join(tickers)} 的关键洞察"
            f"2. 分析师之间的共识点"
            f"3. 存在分歧的观点"
            f"4. 需要进一步关注的风险因素"
            f"5. 初步倾向：基于现有信息，给出综合投资方向判断（强烈推荐/推荐/中性/谨慎/回避）及理由"
        )
        summary_msg = Msg(name="system", content=summary_prompt, role="user")
        summary_response = await _retry_with_backoff(
            lambda: self.pm.reply(summary_msg),
            max_retries=3,
        )

        conference_summary = self._extract_text_content(summary_response.content)

        if self.state_sync:
            await self.state_sync.on_conference_message(
                agent_id="conference_summary",
                content=conference_summary,
            )
            await self.state_sync.on_conference_end()

        return conference_summary

    def _build_pm_discussion_prompt(
        self,
        cycle: int,
        tickers: List[str],
        date: str,
        analyst_results: List[Dict[str, Any]],
        risk_assessment: Dict[str, Any],
    ) -> str:
        """Build PM discussion prompt with full context"""
        if cycle == 0:
            # First cycle: provide full context
            context_lines = [
                f"作为投资组合经理，请审阅以下 {date} 的分析信息：",
                "",
                "=== 分析师信号 ===",
            ]

            for result in analyst_results:
                agent_name = result.get("agent", "Unknown")
                content = result.get("content", "")
                if isinstance(content, str):
                    content_summary = content[:300] + "..." if len(content) > 300 else content
                else:
                    content_summary = str(content)[:300]
                context_lines.append(f"{agent_name}: {content_summary}")

            context_lines.extend([
                "",
                "=== 风险评估 ===",
                str(risk_assessment.get("content", ""))[:300],
                "",
                f"基于以上信息，请分享你对 {', '.join(tickers)} 投资价值的关键问题或疑虑。",
                "这是讨论阶段，暂不做最终决定。",
            ])

            return "\n".join(context_lines)
        else:
            return (
                f"继续讨论。请就其他分析师提出的观点发表看法，"
                f"并分享对 {', '.join(tickers)} 的任何剩余疑虑。"
            )

    def _build_analyst_discussion_prompt(
        self,
        cycle: int,
        tickers: List[str],
        date: str,
        analyst_results: Optional[List[Dict[str, Any]]] = None,
        risk_assessment: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build analyst discussion prompt with full context from other agents"""
        parts = []

        if cycle == 0:
            # 第一轮：提供完整的分析师评估和风险评估摘要
            parts.append("=== 投资分析会议第一轮 ===")
            parts.append("")
            parts.append("以下是各分析师的初步评估摘要，请在此基础上进行讨论：")
            parts.append("")

            if analyst_results:
                parts.append("--- 分析师评估 ---")
                for result in analyst_results:
                    agent_name = result.get("agent", "Unknown")
                    content = self._extract_text_content(result.get("content", ""))[:800]
                    parts.append(f"[{agent_name}] {content}")
                    parts.append("")

            if risk_assessment:
                risk_content = self._extract_text_content(
                    risk_assessment.get("content", "")
                )[:500]
                if risk_content:
                    parts.append("--- 风险评估 ---")
                    parts.append(f"[风险经理] {risk_content}")
                    parts.append("")

            parts.extend([
                f"请就 {', '.join(tickers)} 的投资价值发表你的专业意见。",
                "重点关注你与其他分析师观点的分歧或共识。",
            ])
        else:
            # 后续轮次：引用上一轮的讨论要点
            parts.append(f"=== 投资分析会议第 {cycle + 1} 轮 ===")
            parts.append(
                f"继续讨论。请就其他分析师和风险管理提出的观点发表看法，"
                f"并分享对 {', '.join(tickers)} 的任何剩余疑虑。"
            )

        return "\n".join(parts)

    async def _collect_final_predictions(
        self,
        tickers: List[str],
        date: str,
    ) -> List[Dict[str, Any]]:
        """
        Collect final predictions from all analysts.
        """
        _log(f"Phase 4: Collecting predictions from {len(self.analysts)} analysts")
        final_predictions = []

        for i, analyst in enumerate(self.analysts):
            _log(f"  Collecting prediction from {analyst.name} ({i+1}/{len(self.analysts)})")

            prompt = (
                f"基于你的分析，请提供 {date} 的最终预测。"
                f"对于每个标的 ({', '.join(tickers)})，"
                f"请严格按照以下 JSON 格式输出预测结果（不要输出其他内容）：\n"
                f"{{\n"
                f'  "predictions": [\n'
                f'    {{"ticker": "000001", "direction": "up", "confidence": 0.8, "reason": "理由"}},\n'
                f'    {{"ticker": "600519", "direction": "down", "confidence": 0.6, "reason": "理由"}}\n'
                f"  ]\n"
                f"}}\n\n"
                f"direction 只能是: up（看涨）/ down（看跌）/ neutral（中性）\n"
                f"confidence 范围: 0.0-1.0\n"
                f"不要使用 Markdown 代码块，直接输出 JSON。"
            )

            msg = Msg(name="system", content=prompt, role="user")
            response = await _retry_with_backoff(
                lambda a=analyst, m=msg: a.reply(m),
                max_retries=3,
            )

            content = self._extract_text_content(response.content)
            predictions_data = self._parse_predictions_structured(content, tickers)

            final_predictions.append({
                "agent": analyst.name,
                "predictions": predictions_data,
                "raw_content": content,
            })

        return final_predictions

    def _parse_predictions_structured(
        self,
        content: str,
        tickers: List[str],
    ) -> List[Dict[str, Any]]:
        """
        尝试从结构化输出（JSON）中解析预测，失败则回退到启发式解析。
        """
        # 策略1: 尝试解析 JSON
        cleaned = content.strip()
        # 去除可能的 Markdown 代码块标记
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            predictions_list = parsed.get("predictions", [])
            valid_directions = {"up", "down", "neutral"}

            results = []
            for p in predictions_list:
                ticker = p.get("ticker", "").strip()
                direction = p.get("direction", "neutral").strip().lower()
                confidence = float(p.get("confidence", 0.5))

                if direction not in valid_directions:
                    direction = "neutral"
                if not (0.0 <= confidence <= 1.0):
                    confidence = 0.5

                results.append({
                    "ticker": ticker,
                    "direction": direction,
                    "confidence": confidence,
                    "reason": p.get("reason", ""),
                })

            if results:
                _log(f"Parsed {len(results)} predictions from JSON output")
                return results
        except (json.JSONDecodeError, ValueError, TypeError):
            _log("JSON parsing failed, falling back to heuristic parsing")

        # 策略2: 回退到启发式解析
        return self._parse_predictions_heuristic(content, tickers)

    def _parse_predictions_heuristic(
        self,
        content: str,
        tickers: List[str],
    ) -> List[Dict[str, Any]]:
        """
        启发式解析（原有逻辑改进版）：
        不再依赖股票代码附近的上下文窗口，而是使用正则匹配
        各方向的关键词。
        """
        predictions = []
        content_lower = content.lower()

        # 方向关键词映射
        direction_map = {
            "up": ["up", "bullish", "long", "buy", "看涨", "买入", "推荐", "增持", "强烈买入"],
            "down": ["down", "bearish", "short", "sell", "看跌", "卖出", "减持", "强烈卖出"],
        }

        for ticker in tickers:
            direction = "neutral"
            confidence = 0.5
            ticker_lower = ticker.lower()

            # 检查文本中是否出现该股票及方向关键词
            up_score = 0
            down_score = 0

            for keyword in direction_map["up"]:
                if keyword in content_lower:
                    up_score += 1
            for keyword in direction_map["down"]:
                if keyword in content_lower:
                    down_score += 1

            # 如果包含股票代码，增强匹配权重
            if ticker_lower in content_lower:
                up_score *= 2
                down_score *= 2

            if up_score > down_score and up_score >= 1:
                direction = "up"
                # 根据关键词数量动态调整置信度
                confidence = min(0.9, 0.5 + up_score * 0.1)
            elif down_score > up_score and down_score >= 1:
                direction = "down"
                confidence = min(0.9, 0.5 + down_score * 0.1)

            predictions.append({
                "ticker": ticker,
                "direction": direction,
                "confidence": confidence,
                "reason": "",
            })

        return predictions

    async def _run_analysts_with_sync(
        self,
        tickers: List[str],
        date: str,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run all analysts with real-time sync after each completion"""
        results = []

        for analyst in self.analysts:
            content = (
                f"请分析以下股票 (日期: {date}): {', '.join(tickers)}。"
                f"提供投资信号、置信度评分和分析理由。"
                f"请从你的专业角度进行深入分析。"
            )
            
            if market_data:
                content += f"\n\n市场数据参考:\n{json.dumps(market_data, indent=2, ensure_ascii=False)}"

            msg = Msg(
                name="system",
                content=content,
                role="user",
                metadata={"tickers": tickers, "date": date},
            )

            result = await _retry_with_backoff(
                lambda a=analyst, m=msg: a.reply(m),
                max_retries=3,
            )
            extracted = self._extract_result_from_msg(result)
            results.append(extracted)

            await self._sync_memory_if_retrieved(analyst)

            text_content = self._extract_text_content(result.content)
            if self.state_sync:
                await self.state_sync.on_agent_complete(
                    agent_id=analyst.name,
                    content=text_content,
                )

            # 持久化分析师输出
            await self._persist_agent_output(
                agent_id=analyst.name,
                agent_type="analyst",
                phase="analysis",
                content=text_content,
            )

        return results

    async def _run_risk_manager_with_sync(
        self,
        tickers: List[str],
        date: str,
        market_data: Optional[Dict[str, Any]],
        analyst_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run risk manager assessment with real-time sync"""
        context = {
            "tickers": tickers,
            "date": date,
        }

        if market_data:
            context["market_data"] = market_data

        # 附加分析师评估结果，让风险评估有数据基础
        if analyst_results:
            context["analyst_summaries"] = {
                r["agent"]: self._extract_text_content(r.get("content", ""))[:500]
                for r in analyst_results
            }

        content = (
            f"请评估以下投资标的的风险:\n"
            f"{json.dumps(context, indent=2, ensure_ascii=False)}\n"
            f"请结合分析师评估结果，提供风险警示和建议。"
        )

        msg = Msg(name="system", content=content, role="user")
        result = await _retry_with_backoff(
            lambda: self.risk_manager.reply(msg),
            max_retries=3,
        )
        extracted = self._extract_result_from_msg(result)

        await self._sync_memory_if_retrieved(self.risk_manager)

        text_content = self._extract_text_content(result.content)
        if self.state_sync:
            await self.state_sync.on_agent_complete(
                agent_id="risk_manager",
                content=text_content,
            )

        # 持久化风险评估输出
        await self._persist_agent_output(
            agent_id="risk_manager",
            agent_type="risk",
            phase="risk_assessment",
            content=text_content,
        )

        return extracted

    async def _run_pm_recommendations(
        self,
        tickers: List[str],
        date: str,
        analyst_results: List[Dict[str, Any]],
        risk_assessment: Dict[str, Any],
        final_predictions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run PM to generate investment recommendations"""
        context = {
            "analyst_signals": {
                r["agent"]: self._extract_text_content(r.get("content", ""))[:2000]
                for r in analyst_results
            },
            "risk_warnings": self._extract_text_content(risk_assessment.get("content", ""))[:2000],
            "tickers": tickers,
        }

        # Add conference summary if available (保留足够长度以包含结论)
        if self.conference_summary:
            context["conference_summary"] = self.conference_summary[:3000]

        # Add final predictions summary
        predictions_summary = {}
        for pred in final_predictions:
            agent = pred.get("agent", "Unknown")
            preds = pred.get("predictions", [])
            predictions_summary[agent] = {
                p["ticker"]: f"{p['direction']} ({p['confidence']*100:.0f}%)"
                for p in preds
            }
        context["analyst_predictions"] = predictions_summary

        content = (
            f"基于分析师信号、风险评估和会议讨论，"
            f"请为 {date} 的投资标的提供投资建议。\n\n"
            f"背景信息:\n{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
            f"请为每个标的 ({', '.join(tickers)}) 提供结构化投资建议，"
            f"严格按照以下JSON格式输出（不要添加其他文字）：\n"
            f"```json\n"
            f'{{\n'
            f'  "recommendations": [\n'
            f'    {{\n'
            f'      "ticker": "股票代码",\n'
            f'      "rating": "强烈推荐/推荐/中性/谨慎/回避",\n'
            f'      "target_price": 目标价位（数字，如无则为null），\n'
            f'      "target_price_range": "目标价位区间（如 10.0-12.0）",\n'
            f'      "holding_period": "短期/中期/长期",\n'
            f'      "core_logic": "核心投资逻辑（1-2句）",\n'
            f'      "risk_warnings": "主要风险提示（1-2句）"\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n'
            f"```\n\n"
            f"重要约束：\n"
            f"- 评级必须与会议摘要中的初步倾向一致。如果会议倾向谨慎/回避，评级不得为推荐/强烈推荐\n"
            f"- 目标价位必须与评级方向一致：推荐/强烈推荐时目标价应高于现价，谨慎/回避时目标价应低于现价\n"
            f"- 如果分析师预测方向多数为down，评级应为谨慎或回避\n"
            f"- 如果分析师预测方向多数为up，评级应为推荐或强烈推荐\n"
        )

        msg = Msg(name="system", content=content, role="user")
        result = await _retry_with_backoff(
            lambda: self.pm.reply(msg),
            max_retries=3,
        )
        extracted = self._extract_result_from_msg(result)

        # 一致性校验：检查评级与预测方向、目标价位是否矛盾
        extracted = self._validate_and_fix_recommendation(
            extracted, final_predictions, tickers
        )

        await self._sync_memory_if_retrieved(self.pm)

        text_content = self._extract_text_content(result.content)
        if self.state_sync:
            await self.state_sync.on_agent_complete(
                agent_id="portfolio_manager",
                content=text_content,
            )

        # 持久化 PM 投资建议输出
        await self._persist_agent_output(
            agent_id="portfolio_manager",
            agent_type="pm",
            phase="investment_recommendation",
            content=text_content,
        )

        return extracted

    def _extract_result_from_msg(self, msg: Msg) -> Dict[str, Any]:
        """Extract result dictionary from Msg object（content 统一为纯文本）"""
        plain = self._extract_text_content(msg.content)
        result = {
            "agent": msg.name,
            "content": plain,
            "content_raw": msg.content,
        }

        if hasattr(msg, "metadata") and msg.metadata:
            # metadata 不覆盖已清洗的 content
            meta = dict(msg.metadata)
            meta.pop("content", None)
            result.update(meta)

        if plain:
            try:
                result["content_parsed"] = json.loads(plain)
            except (json.JSONDecodeError, TypeError):
                pass

        return result

    # ============================================================
    # 投资建议一致性校验
    # ============================================================

    # 评级方向映射
    _BULLISH_RATINGS = {"强烈推荐", "推荐"}
    _BEARISH_RATINGS = {"谨慎", "回避"}

    def _validate_and_fix_recommendation(
        self,
        recommendation_result: Dict[str, Any],
        final_predictions: List[Dict[str, Any]],
        tickers: List[str],
    ) -> Dict[str, Any]:
        """
        校验并修正投资建议，确保评级与分析师预测方向和目标价位一致。

        校验规则：
        1. 如果多数分析师预测方向为 down，评级不得为 推荐/强烈推荐
        2. 如果多数分析师预测方向为 up，评级不得为 谨慎/回避
        3. 如果会议摘要包含谨慎/回避倾向，评级不得为 推荐/强烈推荐
        4. 目标价位与评级方向矛盾时添加警告
        """
        content = recommendation_result.get("content", "")
        if not isinstance(content, str) or not content:
            return recommendation_result

        # --- 1. 从分析师预测中统计方向 ---
        up_count = 0
        down_count = 0
        for pred in final_predictions:
            for p in pred.get("predictions", []):
                d = p.get("direction", "neutral")
                if d == "up":
                    up_count += 1
                elif d == "down":
                    down_count += 1

        # --- 2. 从会议摘要中提取倾向 ---
        summary_cautious = False
        if self.conference_summary:
            for keyword in ["谨慎", "回避", "看空", "卖出", "减持", "不建议"]:
                if keyword in self.conference_summary:
                    summary_cautious = True
                    break
        summary_bullish = False
        if self.conference_summary:
            for keyword in ["强烈推荐", "看多", "买入", "增持", "推荐配置"]:
                if keyword in self.conference_summary:
                    summary_bullish = True
                    break

        # --- 3. 从PM输出中提取评级和目标价 ---
        detected_rating = None
        for rating in ["强烈推荐", "推荐", "中性", "谨慎", "回避"]:
            if rating in content:
                detected_rating = rating
                break

        # 提取目标价位
        target_price = None
        import re
        tp_match = re.search(r'目标价[位格]?[：:]?\s*([\d.]+)', content)
        if tp_match:
            try:
                target_price = float(tp_match.group(1))
            except ValueError:
                pass

        # --- 4. 一致性校验和修正 ---
        warnings = []
        needs_fix = False
        fixed_rating = detected_rating

        # 规则A: 多数分析师看空 → 评级不得为看多
        if down_count > up_count and detected_rating in self._BULLISH_RATINGS:
            warnings.append(
                f"⚠️ 评级矛盾：{down_count}位分析师看空 vs {up_count}位看多，"
                f"但评级为「{detected_rating}」，已修正为「谨慎」"
            )
            fixed_rating = "谨慎"
            needs_fix = True

        # 规则B: 多数分析师看多 → 评级不得为看空
        if up_count > down_count and detected_rating in self._BEARISH_RATINGS:
            warnings.append(
                f"⚠️ 评级矛盾：{up_count}位分析师看多 vs {down_count}位看空，"
                f"但评级为「{detected_rating}」，已修正为「推荐」"
            )
            fixed_rating = "推荐"
            needs_fix = True

        # 规则C: 会议摘要倾向谨慎 → 评级不得为看多
        if summary_cautious and not summary_bullish and detected_rating in self._BULLISH_RATINGS:
            warnings.append(
                f"⚠️ 评级与会议倾向矛盾：会议摘要倾向谨慎/回避，"
                f"但评级为「{detected_rating}」，已修正为「中性」"
            )
            fixed_rating = "中性"
            needs_fix = True

        # 规则D: 目标价远低于现价但评级为看多 → 警告
        if target_price is not None and detected_rating in self._BULLISH_RATINGS:
            # 尝试获取现价（从分析师结果中）
            for pred in final_predictions:
                for p in pred.get("predictions", []):
                    current = p.get("current_price")
                    if current and target_price < float(current) * 0.85:
                        warnings.append(
                            f"⚠️ 目标价矛盾：目标价 {target_price} 远低于现价 {current}，"
                            f"但评级为「{detected_rating}」"
                        )
                        if not needs_fix:
                            fixed_rating = "中性"
                            needs_fix = True
                        break

        # --- 5. 应用修正 ---
        if needs_fix and fixed_rating and detected_rating:
            # 替换文本中的评级
            fixed_content = content.replace(detected_rating, fixed_rating, 1)
            recommendation_result["content"] = fixed_content
            recommendation_result["rating_corrected"] = True
            recommendation_result["original_rating"] = detected_rating
            recommendation_result["fixed_rating"] = fixed_rating

        if warnings:
            recommendation_result["consistency_warnings"] = warnings
            _log(f"Recommendation consistency warnings: {'; '.join(warnings)}")

        return recommendation_result

    def _extract_text_content(self, content: Any) -> str:
        """
        Extract plain text from AgentScope Msg content.

        忽略 thinking / tool 块；兼容：
        - 真正的 list/dict content blocks
        - 被 str() 后的 Python repr：[{'type': 'text', 'text': '...'}]
        - JSON 字符串 content blocks
        """
        if content is None:
            return ""

        # 字符串：可能是纯文本，也可能是序列化后的 content blocks
        if isinstance(content, str):
            return self._extract_text_from_serialized(content)

        if isinstance(content, list):
            texts = []
            for item in content:
                piece = self._extract_text_from_block(item)
                if piece:
                    texts.append(piece)
            return "\n".join(texts).strip()

        if isinstance(content, dict):
            return self._extract_text_from_block(content)

        # Msg / 其它对象
        if hasattr(content, "content"):
            return self._extract_text_content(getattr(content, "content"))
        if hasattr(content, "text"):
            return str(getattr(content, "text") or "")

        return self._extract_text_from_serialized(str(content))

    def _extract_text_from_block(self, item: Any) -> str:
        """从单个 content block 提取可见文本。"""
        if item is None:
            return ""
        if isinstance(item, str):
            return self._extract_text_from_serialized(item)
        if not isinstance(item, dict):
            # 兼容对象属性访问
            item_type = getattr(item, "type", None)
            if item_type in ("thinking", "reasoning", "tool_use", "tool_result"):
                return ""
            text = getattr(item, "text", None)
            if text:
                return str(text)
            return ""

        item_type = item.get("type")
        if item_type in ("thinking", "reasoning", "tool_use", "tool_result"):
            return ""
        if item_type == "text" and item.get("text") is not None:
            return str(item.get("text") or "")
        if "text" in item and item_type is None:
            return str(item.get("text") or "")
        if "content" in item and item_type not in ("thinking", "reasoning"):
            return self._extract_text_content(item.get("content"))
        # 未知 dict：尝试常见字段
        for key in ("output", "message", "value"):
            if key in item and item[key]:
                return self._extract_text_content(item[key])
        return ""

    @staticmethod
    def _unescape_common(s: str) -> str:
        """只处理常见转义，避免 unicode_escape 破坏中文 UTF-8。"""
        return (
            s.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\r", "\r")
            .replace("\\'", "'")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )

    def _extract_text_from_serialized(self, text: str) -> str:
        """
        从字符串中提取报告正文。

        处理历史脏数据：
        [{'type': 'thinking', ...}, {'type': 'text', 'text': '...'}]
        [, {'type': 'text', 'text': '...'}]
        以及 markdown 中残留的 thinking 标记。
        """
        if not text:
            return ""
        raw = text.strip()
        if not raw:
            return ""

        def _try_parse_whole(s: str) -> str:
            # 兼容开头多余逗号：[, {...}]
            s2 = re.sub(r"^\[\s*,", "[", s.strip())
            try:
                parsed = json.loads(s2)
                return self._extract_text_content(parsed)
            except Exception:
                pass
            try:
                import ast

                parsed = ast.literal_eval(s2)
                return self._extract_text_content(parsed)
            except Exception:
                return ""

        # 1) 整段就是 content blocks
        if (raw.startswith("[") and raw.endswith("]")) or (
            raw.startswith("{") and raw.endswith("}")
        ):
            extracted = _try_parse_whole(raw)
            if extracted:
                return extracted

        # 2) 报告中间夹了 blocks：替换每一段
        block_pat = re.compile(
            r"\[\s*,?\s*\{[\s\S]*?['\"]type['\"]\s*:\s*['\"]"
            r"(?:thinking|text|reasoning|tool_use|tool_result)['\"]"
            r"[\s\S]*?\}\s*\]"
        )

        def _replace_block(m: re.Match) -> str:
            inner = m.group(0)
            got = _try_parse_whole(inner)
            if got:
                return "\n" + got + "\n"
            # 正则捞 text
            chunks = re.findall(
                r"['\"]type['\"]\s*:\s*['\"]text['\"]\s*,\s*['\"]text['\"]\s*:\s*['\"]([\s\S]*?)['\"]\s*(?:,|\})",
                inner,
            )
            if chunks:
                return "\n" + "\n".join(self._unescape_common(c) for c in chunks) + "\n"
            return ""

        if block_pat.search(raw):
            raw = block_pat.sub(_replace_block, raw)

        # 3) 仍残留 type/text 结构时，抓所有 text 段
        if re.search(r"['\"]type['\"]\s*:", raw) and re.search(r"['\"]text['\"]\s*:", raw):
            text_chunks = re.findall(
                r"['\"]type['\"]\s*:\s*['\"]text['\"]\s*,\s*['\"]text['\"]\s*:\s*['\"]([\s\S]*?)['\"]\s*(?:,|\})",
                raw,
            )
            if text_chunks:
                return "\n\n".join(self._unescape_common(c) for c in text_chunks).strip()

            loose = re.findall(
                r"['\"]text['\"]\s*:\s*['\"]([\s\S]*?)['\"]\s*(?:,|\})",
                raw,
            )
            if loose:
                best = max(loose, key=len)
                if len(best) > 20:
                    return self._unescape_common(best).strip()

        # 4) 清理残留 thinking 标签
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.I)
        cleaned = re.sub(
            r"\{['\"]type['\"]\s*:\s*['\"]thinking['\"][\s\S]*?\}",
            "",
            cleaned,
        )
        cleaned = re.sub(r"\[\s*,\s*", "[", cleaned)
        cleaned = re.sub(r"\[\s*\]", "", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()