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
# @FileName: pm_agent.py
# @Software: PyCharm

from typing import Any, Dict, List, Optional

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import Toolkit,ToolResponse
from agentscope.message import TextBlock

from .prompt_loader import PromptLoader

# 全局提示词加载器
_prompt_loader = PromptLoader()


class PMAgent(ReActAgent):
    """
    投资组合管理Agent(Portfolio Manager)
    
    负责：
    - 综合分析师意见
    - 主持投资委员会讨论
    - 提供最终投资建议和评级
    """

    def __init__(
        self,
        name: str,
        model: Any,
        formatter: Any,
        config: Optional[Dict[str, Any]] = None,
        long_term_memory: Optional[Any] = None,
    ):
        """
        初始化投资组合管理Agent

        Args:
            name: Agent名称
            model: 大模型实例
            formatter: 消息格式化器
            config: 配置信息
            long_term_memory: 长期记忆
        """
        self.config = config or {}
        self._decisions: Dict[str, Dict] = {}
        toolkit = self._create_toolkit()
        sys_prompt = _prompt_loader.load_prompt("portfolio_manager", "system")

        kwargs = {
            "name": name,
            "sys_prompt": sys_prompt,
            "model": model,
            "formatter": formatter,
            "toolkit": toolkit,
            "memory": InMemoryMemory(),
            "max_iters": 10,
        }

        if long_term_memory:
            kwargs["long_term_memory"] = long_term_memory
            kwargs["long_term_memory_mode"] = "both"

        super().__init__(**kwargs)

    def _create_toolkit(self) -> Toolkit:
        """Create toolkit with decision recording tool"""
        toolkit = Toolkit()
        toolkit.register_tool_function(self._make_decision)
        return toolkit

    def _make_decision(
        self,
        ticker: str,
        action: str,
        quantity: int,
        confidence: int = 50,
        reasoning: str = "",
    ) -> ToolResponse:
        """
        Record an invest decision for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            action: Decision - "long", "short" or "hold"
            quantity: Number of shares to trade (0 for hold)
            confidence: Confidence level 0-100
            reasoning: Explanation for this decision

        Returns:
            ToolResponse confirming decision recorded
        """
        if action not in ["long", "short", "hold"]:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Invalid action: {action}. "
                        "Must be 'long', 'short', or 'hold'.",
                    ),
                ],
            )

        self._decisions[ticker] = {
            "action": action,
            "quantity": quantity if action != "hold" else 0,
            "confidence": confidence,
            "reasoning": reasoning,
        }

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Decision recorded: {action} "
                    f"{quantity} shares of {ticker}"
                    f" (confidence: {confidence}%)",
                ),
            ],
        )

    async def reply(self, x: Msg = None) -> Msg:
        """
        处理消息并返回建议

        Args:
            x: 输入消息

        Returns:
            建议响应消息
        """
        if x is None:
            return Msg(
                name=self.name,
                content="No input provided",
                role="assistant",
            )

        result = await super().reply(x)
        if result.metadata is None:
            result.metadata = {}
        result.metadata["decisions"] = self._decisions.copy()

        return result

    def reset_decisions(self) -> None:
        """Reset accumulated decisions (call only when starting a new analysis cycle)"""
        self._decisions = {}

    def get_decisions(self) -> Dict[str, Dict]:
        """Get decisions from current cycle"""
        return self._decisions.copy()
