# -*- coding: utf-8 -*-
# @Time: 2026/1/27 14:01
# @Author : aceplus
# @Desc : ==============================================
# Life is Short I Use Python!!!                      ===
# If this runs wrong,don't ask me,I don't know why.  ===
# If this runs right,thank god,and I don't know why. ===
# Maybe the answer,my friend,is blowing in the wind. ===
# ======================================================
# @Project : ZHANGXJ
# @FileName: analyst.py
# @Software: PyCharm


from typing import Any, Dict, Optional

from backend.config.constants import ANALYST_TYPES

from agentscope.agent import ReActAgent
from agentscope.memory import  InMemoryMemory, LongTermMemoryBase
from agentscope.message import Msg
from agentscope.tool import Toolkit,ToolResponse
from .prompt_loader import PromptLoader

# 全局提示词加载器
_prompt_loader = PromptLoader()

class AnalystAgent(ReActAgent):
    """
    分析Agent，使用大模型自主选择工具进行分析
    """
    def __init__(
            self,
            analyst_type: str,
            toolkit: Any,
            model: Any,
            formatter: Any,
            agent_id: Optional[str] = None,
            config: Optional[Dict[str, Any]] = None,
            long_term_memory: Optional[Any] = None,
        ):
        """
        初始化智能体
        :param analyst_type:分析师类型
        :param toolkit:工具集
        :param model: 大模型
        :param formatter:消息格式化器
        :param agent_id:
        :param config:
        :param long_term_memory:

        fundamentals：基本面分析师（财务健康、盈利能力、增长质量）
        valuation：估值分析师（DCF、剩余收益、EV/EBITDA）
        """

        if analyst_type not in ANALYST_TYPES:
            raise ValueError(
                f"未知的分析师类型: {analyst_type}. "
                f"必须是下面的其中一个: {list(ANALYST_TYPES.keys())}",
            )
        self.analyst_type_key = analyst_type
        self.analyst_persona = ANALYST_TYPES[analyst_type]["display_name"]
        if agent_id is None:
            agent_id = analyst_type

        self.config = config or {}

        sys_prompt = self._load_system_prompt()
        kwargs = {
            "name": agent_id,
            "sys_prompt": sys_prompt,
            "model": model,
            "formatter": formatter,
            "toolkit": toolkit,
            "memory": InMemoryMemory(),
            "max_iters": 10,
        }

        if long_term_memory:
            kwargs["long_term_memory"] = long_term_memory
            kwargs["long_term_memory_mode"] = "static_control"

        super().__init__(**kwargs)

    def _load_system_prompt(self) -> str:
        """为分析师加载系统提示词"""
        personas_config = _prompt_loader.load_yaml_config(
            "analyst",
            "personas",
        )
        persona = personas_config.get(self.analyst_type_key, {})

        # Get focus items and format as bullet points
        focus_items = persona.get("focus", [])
        focus_text = "\n".join(f"- {item}" for item in focus_items)

        # Get description
        description = persona.get("description", "").strip()

        # Get tools guidance
        tools_guidance = persona.get("tools_guidance", "").strip()

        return _prompt_loader.load_prompt(
            "analyst",
            "system",
            variables={
                "analyst_type": self.analyst_persona,
                "focus": focus_text,
                "description": description,
                "tools_guidance": tools_guidance,
            },
        )
    async def reply(self, x: Msg = None) -> Msg:
        """
        Override reply method to add progress tracking

        Args:
            x: Input message (content must be str)

        Returns:
            Response message (content is str)
        """
        ticker = None
        if x and hasattr(x, "metadata") and x.metadata:
            ticker = x.metadata.get("tickers")

        # if ticker:
        #     progress.update_status(
        #         self.name,
        #         ticker,
        #         f"Starting {self.analyst_persona} analysis",
        #     )

        result = await super().reply(x)

        # if ticker:
        #     progress.update_status(
        #         self.name,
        #         ticker,
        #         "Analysis completed",
        #     )

        return result
