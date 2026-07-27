# -*- coding: utf-8 -*-
# @Time: 2026/1/28 13:52
# @Author : aceplus
# @Desc : ==============================================
# Life is Short I Use Python!!!                      ===
# If this runs wrong,don't ask me,I don't know why.  ===
# If this runs right,thank god,and I don't know why. ===
# Maybe the answer,my friend,is blowing in the wind. ===
# ======================================================
# @Project : ZHANGXJ
# @FileName: risk_agent.py
# @Software: PyCharm

from typing import Any, Dict, List, Optional

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import Toolkit,ToolResponse
from .prompt_loader import PromptLoader

# 全局提示词加载器
_prompt_loader = PromptLoader()


class RiskAgent(ReActAgent):
    """
    风险管理Agent，评估投资组合风险并提供风险预警
    """

    def __init__(
        self,
        model: Any,
        formatter: Any,
        name: str = "risk_manager",
        config: Optional[Dict[str, Any]] = None,
        long_term_memory: Optional[Any] = None,
    ):
        """
        初始化风险管理Agent

        Args:
            model: 大模型实例
            formatter: 消息格式化器
            name: Agent名称
            config: 配置信息
            long_term_memory: 长期记忆
        """
        self.config = config or {}

        sys_prompt = _prompt_loader.load_prompt("risk_manager", "system")

        # 创建工具包并注册风险评估工具
        toolkit = Toolkit()
        toolkit.register_tool_function(self._tool_assess_financial_risk)
        toolkit.register_tool_function(self._tool_assess_concentration_risk)

        kwargs = {
            "name": name,
            "sys_prompt": sys_prompt,
            "model": model,
            "formatter": formatter,
            "toolkit": toolkit,
            "memory": InMemoryMemory(),
            "max_iters": 5,
        }

        if long_term_memory:
            kwargs["long_term_memory"] = long_term_memory
            kwargs["long_term_memory_mode"] = "static_control"

        super().__init__(**kwargs)


    async def reply(self, x: Msg = None) -> Msg:
        """
        处理消息并返回风险评估

        Args:
            x: 输入消息

        Returns:
            风险评估响应消息
        """
        result = await super().reply(x)
        return result

    def _tool_assess_financial_risk(
        self,
        financial_data: Dict[str, Any],
    ) -> ToolResponse:
        """
        基于财务数据分析个股风险

        Args:
            financial_data: 包含各维度分析结果的字典，键包括
                profitability, solvency, growth, operating

        Returns:
            风险评估结果
        """
        warnings = []
        risk_score = 0.0  # 0-100, 越高越危险

        # 1. 偿债能力分析
        solvency = financial_data.get("solvency", {})
        indicators = solvency.get("indicators", [])
        if indicators:
            latest = indicators[-1]
            debt_ratio = latest.get("debt_ratio", 0)
            if debt_ratio > 70:
                warnings.append(f"资产负债率过高: {debt_ratio:.1f}%")
                risk_score += 25
            elif debt_ratio > 60:
                warnings.append(f"资产负债率偏高: {debt_ratio:.1f}%")
                risk_score += 15

            current_ratio = latest.get("current_ratio", 0)
            if current_ratio < 0.8:
                warnings.append(f"流动比率过低: {current_ratio:.2f}")
                risk_score += 20
            elif current_ratio < 1.0:
                warnings.append(f"流动比率偏低: {current_ratio:.2f}")
                risk_score += 10

        # 2. 盈利能力分析
        profitability = financial_data.get("profitability", {})
        prof_indicators = profitability.get("indicators", [])
        if prof_indicators:
            latest = prof_indicators[-1]
            roe = latest.get("roe", 0)
            if roe < 5:
                warnings.append(f"ROE偏低: {roe:.2f}%")
                risk_score += 10
            elif roe < 0:
                warnings.append(f"ROE为负: {roe:.2f}%")
                risk_score += 20

            gross_margin = latest.get("gross_margin", 0)
            if gross_margin < 15:
                warnings.append(f"毛利率偏低: {gross_margin:.1f}%")
                risk_score += 10

        # 3. 增长分析
        growth = financial_data.get("growth", {})
        growth_indicators = growth.get("indicators", [])
        if growth_indicators:
            latest = growth_indicators[-1]
            revenue_growth = latest.get("revenue_growth", 0)
            profit_growth = latest.get("profit_growth", 0)
            if revenue_growth < 0 and profit_growth < 0:
                warnings.append("营收和净利润双降")
                risk_score += 15
            elif revenue_growth < 5:
                warnings.append(f"营收增速偏低: {revenue_growth:.1f}%")
                risk_score += 5

        # 4. 营运能力分析
        operating = financial_data.get("operating", {})
        op_indicators = operating.get("indicators", [])
        if op_indicators:
            latest = op_indicators[-1]
            inventory_turnover = latest.get("inventory_turnover_days", 999)
            if inventory_turnover > 200:
                warnings.append(f"存货周转天数过长: {inventory_turnover:.0f}天")
                risk_score += 10

        # 确定风险等级
        if risk_score >= 50:
            risk_level = "HIGH"
        elif risk_score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return ToolResponse(
            content=[
                ToolResponse.text(
                    f"财务风险评估: 风险等级={risk_level}, "
                    f"风险分数={risk_score:.0f}/100\n"
                    f"警告项: {'; '.join(warnings) if warnings else '无显著风险'}"
                )
            ],
        )

    def _tool_assess_concentration_risk(
        self,
        portfolio: Dict[str, Any],
    ) -> ToolResponse:
        """
        评估投资组合集中度风险

        Args:
            portfolio: 投资组合信息，包含 positions 字典 {ticker: weight}

        Returns:
            集中度风险评估结果
        """
        positions = portfolio.get("positions", {})
        if not positions:
            return ToolResponse(
                content=[ToolResponse.text("无持仓数据，无法评估集中度风险")]
            )

        total = sum(positions.values())
        if total == 0:
            return ToolResponse.text("持仓总权重为零，无法评估集中度风险")

        # 计算HHI
        weights = [v / total for v in positions.values()]
        hhi = sum(w ** 2 for w in weights)

        # 计算最大单一持仓占比
        max_weight = max(weights) * 100

        # HHI 解释: < 1500 低集中, 1500-2500 中等, > 2500 高集中
        if hhi > 0.25:
            concentration = "HIGH"
            msg = f"高度集中 (HHI={hhi:.4f})"
        elif hhi > 0.15:
            concentration = "MEDIUM"
            msg = f"中度集中 (HHI={hhi:.4f})"
        else:
            concentration = "LOW"
            msg = f"分散良好 (HHI={hhi:.4f})"

        details = [
            f"持仓数量: {len(positions)}",
            f"最大持仓: {max_weight:.1f}%",
            f"集中度: {msg}",
        ]

        return ToolResponse(
            content=[ToolResponse.text(f"集中度风险: {concentration}\n" + "\n".join(details))]
        )

    def assess_portfolio_risk(
        self,
        portfolio: Dict[str, Any],
        prices: Dict[str, float],
        tickers: list,
    ) -> Dict[str, Any]:
        """
        评估投资组合风险（同步方法，用于快速风险检查）

        Args:
            portfolio: 当前投资组合状态
            prices: 当前价格
            tickers: 股票代码列表

        Returns:
            风险评估结果
        """
        risk_assessment = {
            "overall_risk_level": "MEDIUM",
            "portfolio_concentration": self._calculate_concentration(portfolio),
            "individual_risks": {},
            "warnings": [],
            "recommendations": [],
        }

        # 评估每只股票的风险（基于持仓权重）
        positions = portfolio.get("positions", {})
        for ticker in tickers:
            weight = positions.get(ticker, 0)
            risk_level = "LOW"
            factors = []

            # 根据持仓集中度判断
            total_value = sum(positions.values()) if positions else 1
            if total_value > 0 and weight / total_value > 0.4:
                risk_level = "MEDIUM"
                factors.append("持仓集中度较高")

            # 根据价格波动判断（如有数据）
            if ticker in prices and prices[ticker] <= 0:
                risk_level = "HIGH"
                factors.append("价格为非正值，数据异常")

            risk_assessment["individual_risks"][ticker] = {
                "risk_level": risk_level,
                "factors": factors,
            }
            risk_assessment["warnings"].extend(
                [f"{ticker}: {', '.join(factors)}" if factors else f"{ticker}: 无明显风险"]
            )

        return risk_assessment

    def _calculate_concentration(self, portfolio: Dict[str, Any]) -> float:
        """计算投资组合集中度"""
        positions = portfolio.get("positions", {})
        if not positions:
            return 0.0

        # 简单的Herfindahl指数计算
        total_value = sum(positions.values())
        if total_value == 0:
            return 0.0

        hhi = sum((v / total_value) ** 2 for v in positions.values())
        return hhi
