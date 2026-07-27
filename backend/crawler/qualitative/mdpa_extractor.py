# -*- coding: utf-8 -*-
"""
MD&A 结构化提取器

将 MinerU 输出的 Markdown 格式年报，按章节结构提取为结构化字段。

巨潮资讯网的年报 PDF 经过 MinerU 解析后，会保留章节标题结构：
```markdown
# 第三节 管理层讨论与分析

## 一、经营情况讨论与分析
公司全年实现营业收入...

## 二、核心竞争力分析
公司在行业内保持领先...

## 三、风险因素
1. 宏观经济风险...
2. 行业竞争风险...

## 四、未来展望
公司计划在...
```

本模块负责将此 Markdown 解析为：
{
    "overview": "...",
    "revenue_analysis": "...",
    "core_competencies": "...",
    "risk_factors": "...",
    "risk_keywords": ["宏观", "竞争", "汇率"],
    "future_outlook": "...",
    "capacity_plans": "..."
}
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MDAExtractor:
    """
    MD&A (管理层讨论与分析) 结构化提取器

    从 Markdown 文本中提取年报/季报的结构化段落。
    支持中英文标题（巨潮年报可能是中文或英文）。
    """

    # 目标章节的正则模式
    # 注意：真实年报标题序号不固定（一/二/三… 或 (一)/(二)…），
    # 以关键词匹配为主。使用命名捕获 (?P<content>...) 提取正文。
    # 截止到下一个同级 ## 标题（允许子标题 ###/#### 被包含在内）。
    _H = r"(?P<header>#{1,4})\s*"
    # 截止：下一个 ## 级标题或文本结束（允许 ###/#### 子标题内容被包含）
    _STOP = r"(?=\n##\s|\Z)"

    SECTION_PATTERNS = {
        "overview": [
            rf"{_H}[^\n]*经营情况讨论与分析[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*管理层讨论与分析[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*经营情况分析[^\n]*\n(?P<content>.*?){_STOP}",
            r"##\s*Management Discussion & Analysis\s*\n(?P<content>.*?)(?=##\s*|$)",
        ],
        "revenue_analysis": [
            rf"{_H}[^\n]*主营业务分析[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*(?:业务回顾|收入和利润分析|经营成果分析|报告期内主要经营情况)[^\n]*\n(?P<content>.*?){_STOP}",
            r"###\s*(?:Revenue\s+Analysis|Business\s+Review)\s*\n(?P<content>.*?)(?=###\s*|$)",
        ],
        "cost_analysis": [
            rf"{_H}[^\n]*成本分析[^\n]*\n(?P<content>.*?){_STOP}",
            r"###\s*(?:Cost\s+Analysis)\s*\n(?P<content>.*?)(?=###\s*|$)",
        ],
        "rd_investment": [
            rf"{_H}[^\n]*研发投入[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*研发支出[^\n]*\n(?P<content>.*?){_STOP}",
            r"###\s*(?:R&D\s+Investment|Research\s+and\s+Development)\s*\n(?P<content>.*?)(?=###\s*|$)",
        ],
        "core_competencies": [
            rf"{_H}[^\n]*核心竞争力[^\n]*\n(?P<content>.*?){_STOP}",
            r"##\s*(?:Core\s+Competitiveness\s+Analysis|Core\s+Competencies)\s*\n(?P<content>.*?)(?=##\s*|$)",
        ],
        "risk_factors": [
            rf"{_H}[^\n]*可能面对的风险[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*重大风险提示[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*风险因素[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*与金融工具相关的风险[^\n]*\n(?P<content>.*?){_STOP}",
            r"##\s*(?:Risk\s+Factors)\s*\n(?P<content>.*?)(?=##\s*|$)",
        ],
        "future_outlook": [
            rf"{_H}[^\n]*公司关于公司未来发展的讨论与分析[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*未来发展的讨论与分析[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*经营计划[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*未来展望[^\n]*\n(?P<content>.*?){_STOP}",
            rf"{_H}[^\n]*公司未来发展[^\n]*\n(?P<content>.*?){_STOP}",
            r"##\s*(?:Future\s+Outlook|Prospects)\s*\n(?P<content>.*?)(?=##\s*|$)",
        ],
        "capacity_plans": [
            rf"{_H}[^\n]*产能规划[^\n]*\n(?P<content>.*?){_STOP}",
            r"###\s*(?:Capacity\s+Planning|Construction\s+in\s+Progress)\s*\n(?P<content>.*?)(?=###\s*|$)",
        ],
    }

    def extract(self, markdown: str) -> Dict[str, Optional[str]]:
        """
        从 Markdown 文本中提取所有目标章节

        Args:
            markdown: MinerU 输出的完整 Markdown 文本

        Returns:
            {section_name: extracted_text}
        """
        if not markdown or not markdown.strip():
            return {key: None for key in self.SECTION_PATTERNS}

        # 优先在「管理层讨论与分析」章节内提取，减少财务附注误匹配
        mda_scope = self._slice_mda_scope(markdown) or markdown

        result = {}
        for section, patterns in self.SECTION_PATTERNS.items():
            extracted = None
            # 先在 MD&A 范围内找，再回退全文
            for source in (mda_scope, markdown):
                for pattern in patterns:
                    match = re.search(pattern, source, re.DOTALL | re.IGNORECASE)
                    if match:
                        text = match.groupdict().get("content") or ""
                        text = text.strip()
                        # 如果正则匹配到空（标题后紧跟子标题），
                        # 改用位置截取法：从标题行末到下一个同级 ## 标题
                        if len(text) < 20:
                            text = self._extract_by_position(
                                source, match.start(), match.end()
                            )
                        text = re.sub(r'\n{3,}', '\n\n', text)
                        text = re.sub(r'[ \t]+', ' ', text)
                        # 去掉开头的勾选框噪声行（√适用 □不适用 等）
                        text = re.sub(r'^[√□☑☐☒\s适用不适用]+\n*', '', text)
                        # 过滤过短片段
                        if len(text) > 20 and not re.fullmatch(r"[√□适用\s不适用]+", text):
                            extracted = text
                            break
                if extracted:
                    break
            result[section] = extracted

        matched = [k for k, v in result.items() if v]
        logger.info(f"[MDAExtractor] matched sections={matched or 'none'}")
        return result

    @staticmethod
    def _extract_by_position(source: str, match_start: int, match_end: int) -> str:
        """
        正则匹配到标题但 content 为空时，从标题行末尾手动截取到下一个同级标题。

        策略：识别标题中的中文序号（一/二/…/十/十一…），
        截取到下一个同序号级别的标题行。
        """
        # 找到标题行
        line_start = source.rfind('\n', 0, match_start) + 1
        line_end = source.find('\n', match_start)
        if line_end < 0:
            line_end = len(source)
        title_line = source[line_start:line_end]

        # 提取标题中的中文序号，如 "六、" → 6
        cn_num_map = {
            '一':1,'二':2,'三':3,'四':4,'五':5,
            '六':6,'七':7,'八':8,'九':9,'十':10,
            '十一':11,'十二':12,'十三':13,'十四':14,'十五':15,
        }
        current_num = None
        m = re.search(r'([一二三四五六七八九十]{1,2})、', title_line)
        if m:
            current_num = cn_num_map.get(m.group(1))

        # 从标题行末往后扫描
        pos = line_end + 1
        # 跳过空行
        while pos < len(source) and source[pos] in ('\n', ' ', '\t'):
            pos += 1

        if current_num is not None:
            # 找下一个同级序号标题
            next_num = current_num + 1
            next_cn = None
            for cn, n in cn_num_map.items():
                if n == next_num:
                    next_cn = cn
                    break
            if next_cn:
                pat = re.compile(rf'^##\s*{re.escape(next_cn)}、', re.MULTILINE)
                m2 = pat.search(source, pos)
                if m2:
                    return source[pos:m2.start()].strip()

        # 回退：找下一个 ## 级标题（排除紧跟的子标题）
        # 至少跳过 2 行内容
        min_end = pos + 50
        for m2 in re.finditer(r'\n##\s', source[pos:]):
            candidate = pos + m2.start()
            if candidate > min_end:
                return source[pos:candidate].strip()

        return source[pos:].strip()

    @staticmethod
    def _slice_mda_scope(markdown: str) -> Optional[str]:
        """截取「管理层讨论与分析」到下一「第X节」之间的正文。"""
        start = re.search(
            r"^#{1,3}\s*[^\n]*管理层讨论与分析[^\n]*$",
            markdown,
            re.MULTILINE,
        )
        if not start:
            return None
        rest = markdown[start.start():]
        end = re.search(
            r"\n#{1,3}\s*第[四五六七八九十\d]+节\b",
            rest[1:],  # 跳过当前标题
        )
        if end:
            return rest[: end.start() + 1]
        return rest

    def extract_risk_keywords(self, risk_text: Optional[str]) -> List[str]:
        """
        从风险因素文本中提取关键词

        策略：提取带编号的风险项标题，以及高频出现的风险词汇

        Args:
            risk_text: 风险因素章节的文本

        Returns:
            风险关键词列表
        """
        if not risk_text:
            return []

        keywords = []

        # 策略1: 提取带编号的风险项标题
        numbered_patterns = [
            r'(?:\d+[、.．]\s*)([^\n\r]{2,30})(?:风险|因素|挑战|压力|隐患|影响)',
            r'(?:\d+[、.．]\s*)(.{5,20}?[风危挑压隐])',
        ]
        for pattern in numbered_patterns:
            matches = re.findall(pattern, risk_text)
            keywords.extend(matches)

        # 策略2: 提取常见风险关键词
        common_risk_terms = [
            "宏观经济", "行业竞争", "原材料价格", "汇率", "利率",
            "政策变化", "技术迭代", "市场需求", "供应链", "环保",
            "知识产权", "人才流失", "商誉减值", "应收账款", "存货",
            "关联交易", "外汇", "国际贸易", "反垄断", "数据安全",
        ]
        found_terms = [term for term in common_risk_terms if term in risk_text]
        keywords.extend(found_terms)

        # 去重并限制数量
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_clean = kw.strip()
            if kw_clean and kw_clean not in seen and len(kw_clean) > 1:
                seen.add(kw_clean)
                unique_keywords.append(kw_clean)

        return unique_keywords[:20]  # 最多返回20个关键词

    def count_keyword_frequency(self, markdown: str, keywords: List[str]) -> Dict[str, int]:
        """
        统计关键词在全文中出现的次数

        Args:
            markdown: 完整 Markdown 文本
            keywords: 关键词列表

        Returns:
            {keyword: count}
        """
        freq = {}
        text_lower = markdown.lower()
        for kw in keywords:
            count = text_lower.count(kw.lower())
            if count > 0:
                freq[kw] = count
        return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))
