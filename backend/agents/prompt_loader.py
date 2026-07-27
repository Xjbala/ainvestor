# -*- coding: utf-8 -*-
# @Time: 2026/1/27 14:45
# @Author : aceplus
# @Desc : ==============================================
# Life is Short I Use Python!!!                      ===
# If this runs wrong,don't ask me,I don't know why.  ===
# If this runs right,thank god,and I don't know why. ===
# Maybe the answer,my friend,is blowing in the wind. ===
# ======================================================
# @Project : ZHANGXJ
# @FileName: prompt_loader.py.py
# @Software: PyCharm


import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

class PromptLoader:
    """统一提示词管理"""

    def __init__(self, prompts_dir: Optional[Path] = None):
        """初始化提示体
        Args:
            prompts_dir: 提示词目录
        """
        if prompts_dir is None:
            self.prompts_dir = Path(__file__).parent / "prompts"
        else:
            self.prompts_dir = Path(prompts_dir)
        #提示词缓存
        self._prompt_cache: Dict[str, str] = {}
        self._yaml_cache: Dict[str, Dict] = {}

    def load_prompt(
            self,
            agent_type: str,
            prompt_name: str,
            variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        提示词加载器
        Args:
            :param agent_type: Agent类型
            :param prompt_name: 提示词名称
            :param variables: 变量字典
        :return:
            渲染提示词结果
        Examples:
            loader = PromptLoader()
            prompt = loader.load_prompt("analyst", "tool_selection",
            {"analyst_persona": "Technical Analyst"})
        """
        cache_key = f"{agent_type}/{prompt_name}"
        #尝试从缓存中加载
        if cache_key not in self._prompt_cache:
            prompt_path = self.prompts_dir / agent_type / f"{prompt_name}.md"

            if not prompt_path.exists():
                raise FileNotFoundError(
                    f"Prompt file not found: {prompt_path}\n"
                    f"Please create the prompt file or check the path.",
                )

            with open(prompt_path, "r", encoding="utf-8") as f:
                self._prompt_cache[cache_key] = f.read()

        prompt_template = self._prompt_cache[cache_key]

        # 如果提供了变量，使用_render_template 替换
        if variables:
            rendered = self._render_template(prompt_template, variables)
        else:
            rendered = prompt_template

        # Smart escaping: escape braces in JSON code blocks
        # rendered = self._escape_json_braces(rendered)
        return rendered

    def _render_template(
        self,
        template: str,
        variables: Dict[str, Any],
    ) -> str:
        """
        使用字符串替换来渲染模板
        支持 {{ variable }} 语法 (兼容Jinja2 格式)

        Args:
            template: 模板字符串
            variables: 变量字典

        Returns:
            Rendered string
        """
        rendered = template

        # Replace {{ variable }} format
        for key, value in variables.items():
            # Support both {{ key }} and {{key}} formats
            pattern1 = f"{{{{ {key} }}}}"
            pattern2 = f"{{{{{key}}}}}"
            rendered = rendered.replace(pattern1, str(value))
            rendered = rendered.replace(pattern2, str(value))

        return rendered

    def load_yaml_config(
        self,
        agent_type: str,
        config_name: str,
    ) -> Dict[str, Any]:
        """
        YAML配置文件加载

        Args:
            agent_type: agent类型
            config_name: 配置文件名称

        Returns:
            配置字典

        Examples:
            >>> loader = PromptLoader()
            >>> config = loader.load_yaml_config("analyst", "personas")
        """
        cache_key = f"{agent_type}/{config_name}"

        if cache_key not in self._yaml_cache:
            yaml_path = self.prompts_dir / agent_type / f"{config_name}.yaml"

            if not yaml_path.exists():
                raise FileNotFoundError(f"YAML config not found: {yaml_path}")

            with open(yaml_path, "r", encoding="utf-8") as f:
                self._yaml_cache[cache_key] = yaml.safe_load(f)

        return self._yaml_cache[cache_key]

    def clear_cache(self):
        """热加载，清楚缓存"""
        self._prompt_cache.clear()
        self._yaml_cache.clear()

    def reload_prompt(self, agent_type: str, prompt_name: str):
        """重新加载提示词 (强制刷新缓存)"""
        cache_key = f"{agent_type}/{prompt_name}"
        if cache_key in self._prompt_cache:
            del self._prompt_cache[cache_key]

    def reload_config(self, agent_type: str, config_name: str):
        """重新加载配置 (强制刷新缓存)"""
        cache_key = f"{agent_type}/{config_name}"
        if cache_key in self._yaml_cache:
            del self._yaml_cache[cache_key]
