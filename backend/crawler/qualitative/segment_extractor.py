# -*- coding: utf-8 -*-
"""
经营分部 / 主营构成抽取器

从年报 Markdown（MinerU 输出）中解析分部营收/利润表。
优先规则解析；可选 LLM 兜底（需 OPENAI 兼容环境变量）。
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExtractedSegment:
    segment_name: str
    segment_type: str = "product"
    revenue: Optional[float] = None
    operating_income: Optional[float] = None
    ebitda: Optional[float] = None
    revenue_yoy: Optional[float] = None
    raw_snippet: Optional[str] = None
    confidence: str = "medium"


# 章节标题
SECTION_HEADERS = [
    r"按产品[构列]示",
    r"按地区[构列]示",
    r"主营业务分析",
    r"主营构成",
    r"经营分部",
    r"分部信息",
    r"分部报告",
    r"业务分部",
    r"营业收入构成",
    r"分行业情况",
    r"分产品情况",
    r"分地区情况",
]

# 忽略的汇总行
SKIP_NAMES = {
    "合计", "总计", "小计", "汇总", "total", "sum", "eliminations",
    "抵消", "抵销", "分部间抵销", "未分配", "其他未分配", "公司层面",
}


class SegmentExtractor:
    """从 Markdown 抽取分部数据。"""

    def extract(
        self,
        markdown: str,
        *,
        company_code: str = "",
        report_period: Optional[date] = None,
        use_llm_fallback: bool = True,
    ) -> Dict[str, Any]:
        if not markdown or len(markdown) < 50:
            return {
                "company_code": company_code,
                "report_period": report_period.isoformat() if report_period else None,
                "segments": [],
                "confidence": "low",
                "source": "cninfo_pdf",
                "message": "markdown empty",
            }

        sections = self._find_section_blocks(markdown)
        segments: List[ExtractedSegment] = []
        method = "rules"

        for title, block, seg_type in sections:
            parsed = self._parse_tables_in_block(block, default_type=seg_type)
            for p in parsed:
                p.raw_snippet = (p.raw_snippet or title)[:500]
            segments.extend(parsed)

        # 全文再扫一次 markdown 表格（部分年报表格不在标题下）
        if len(segments) < 2:
            for table in self._iter_markdown_tables(markdown):
                parsed = self._parse_markdown_table(table, default_type="product")
                segments.extend(parsed)

        segments = self._dedupe_and_clean(segments)

        if len(segments) < 2 and use_llm_fallback:
            llm_segs = self._llm_extract(markdown, company_code)
            if llm_segs:
                segments = self._dedupe_and_clean(llm_segs)
                method = "llm"

        confidence = "high" if method == "rules" and len(segments) >= 2 else (
            "medium" if len(segments) >= 2 else "low"
        )
        for s in segments:
            s.confidence = confidence

        return {
            "company_code": company_code,
            "report_period": report_period.isoformat() if report_period else None,
            "segments": [asdict(s) for s in segments],
            "confidence": confidence,
            "source": "cninfo_pdf" if method == "rules" else "llm",
            "method": method,
            "count": len(segments),
        }

    def _find_section_blocks(self, markdown: str) -> List[Tuple[str, str, str]]:
        blocks: List[Tuple[str, str, str]] = []
        # 按标题切开
        pattern = re.compile(
            r"(?:^|\n)(#{1,4}\s*[^\n]*(?:" + "|".join(SECTION_HEADERS) + r")[^\n]*)\n",
            re.IGNORECASE,
        )
        matches = list(pattern.finditer(markdown))
        for i, m in enumerate(matches):
            title = m.group(1).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else min(len(markdown), start + 8000)
            body = markdown[start:end]
            seg_type = "region" if re.search(r"地区|区域|region", title, re.I) else "product"
            if re.search(r"行业", title):
                seg_type = "product"
            blocks.append((title, body, seg_type))
        return blocks

    def _iter_markdown_tables(self, text: str) -> List[str]:
        # 连续含 | 的行视为表格
        lines = text.splitlines()
        tables: List[str] = []
        buf: List[str] = []
        for line in lines:
            if "|" in line:
                buf.append(line)
            else:
                if len(buf) >= 3:
                    tables.append("\n".join(buf))
                buf = []
        if len(buf) >= 3:
            tables.append("\n".join(buf))
        return tables

    def _parse_tables_in_block(self, block: str, default_type: str) -> List[ExtractedSegment]:
        out: List[ExtractedSegment] = []
        for table in self._iter_markdown_tables(block):
            out.extend(self._parse_markdown_table(table, default_type=default_type))
        # 也尝试「名称 数字 数字」类文本行
        if not out:
            out.extend(self._parse_loose_lines(block, default_type=default_type))
        return out

    def _parse_markdown_table(self, table: str, default_type: str) -> List[ExtractedSegment]:
        rows = []
        for line in table.splitlines():
            line = line.strip()
            if not line or not line.startswith("|"):
                continue
            if re.match(r"^\|[\s\-:|]+\|$", line):
                continue  # separator
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells:
                rows.append(cells)
        if len(rows) < 2:
            return []

        header = [self._norm_header(h) for h in rows[0]]
        # 判断是否分部相关表
        header_join = " ".join(header)
        if not any(
            k in header_join
            for k in ("产品", "业务", "分部", "地区", "行业", "项目", "名称", "segment", "product", "region")
        ):
            # 可能第一列是名称但表头是「项目」
            if "收入" not in header_join and "营收" not in header_join and "revenue" not in header_join:
                return []

        name_idx = 0
        for i, h in enumerate(header):
            if any(k in h for k in ("产品", "业务", "分部", "地区", "行业", "项目", "名称", "segment")):
                name_idx = i
                break

        rev_idx = self._find_col(header, ["营业收入", "主营业务收入", "收入", "营收", "revenue", "sales"])
        op_idx = self._find_col(header, ["营业利润", "分部利润", "利润", "operating", "profit"])
        yoy_idx = self._find_col(header, ["同比", "增减", "yoy", "增长"])

        # 若表头无法识别收入列，尝试数值列
        if rev_idx is None and len(header) >= 2:
            rev_idx = 1

        segs: List[ExtractedSegment] = []
        for row in rows[1:]:
            if name_idx >= len(row):
                continue
            name = re.sub(r"\s+", "", row[name_idx])
            name = name.replace("**", "").strip()
            if not name or self._is_skip_name(name):
                continue
            rev = self._parse_number(row[rev_idx]) if rev_idx is not None and rev_idx < len(row) else None
            opi = self._parse_number(row[op_idx]) if op_idx is not None and op_idx < len(row) else None
            yoy = self._parse_number(row[yoy_idx], is_ratio=True) if yoy_idx is not None and yoy_idx < len(row) else None
            if rev is None and opi is None:
                continue
            # 单位启发：若数字很小（<1e6）可能是亿元
            rev = self._scale_amount(rev)
            opi = self._scale_amount(opi)
            segs.append(
                ExtractedSegment(
                    segment_name=name[:100],
                    segment_type=default_type,
                    revenue=rev,
                    operating_income=opi,
                    revenue_yoy=yoy,
                    raw_snippet="|".join(row)[:300],
                    confidence="medium",
                )
            )
        return segs

    def _parse_loose_lines(self, block: str, default_type: str) -> List[ExtractedSegment]:
        segs: List[ExtractedSegment] = []
        # 例：云计算  1,234.56  234.5
        for line in block.splitlines():
            line = line.strip()
            if len(line) < 4 or line.startswith("#") or line.startswith("|"):
                continue
            m = re.match(
                r"^([\u4e00-\u9fa5A-Za-z0-9（）()·\-]{2,30})\s+([\d,.\-]+(?:万|亿)?)\s+([\d,.\-]+(?:万|亿)?)?",
                line,
            )
            if not m:
                continue
            name = m.group(1).strip()
            if self._is_skip_name(name):
                continue
            rev = self._scale_amount(self._parse_number(m.group(2)))
            opi = self._scale_amount(self._parse_number(m.group(3))) if m.group(3) else None
            if rev is None:
                continue
            segs.append(
                ExtractedSegment(
                    segment_name=name[:100],
                    segment_type=default_type,
                    revenue=rev,
                    operating_income=opi,
                    raw_snippet=line[:300],
                )
            )
        return segs

    def _llm_extract(self, markdown: str, company_code: str) -> List[ExtractedSegment]:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("SEGMENT_LLM_MODEL") or os.getenv("MODEL_NAME") or "gpt-4o-mini"
        if not api_key:
            logger.debug("LLM segment extract skipped: no API key")
            return []

        # 截取相关片段，控制 token
        snippet = self._relevant_snippet(markdown, max_chars=12000)
        if not snippet:
            return []

        prompt = (
            "你是财务分析助手。从下列 A 股年报 Markdown 中提取「按产品/按地区/经营分部」的分部数据。\n"
            "只返回 JSON 数组，每项字段: segment_name, segment_type(product|region), "
            "revenue(元,数字), operating_income(元,数字可null)。\n"
            "金额请换算为元（注意万/亿）。忽略合计/抵销行。无数据返回 []。\n"
            f"公司: {company_code}\n---\n{snippet}"
        )

        try:
            import urllib.request

            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"]
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            data = json.loads(text)
            if not isinstance(data, list):
                return []
            segs: List[ExtractedSegment] = []
            for item in data:
                name = str(item.get("segment_name") or "").strip()
                if not name or self._is_skip_name(name):
                    continue
                segs.append(
                    ExtractedSegment(
                        segment_name=name[:100],
                        segment_type=item.get("segment_type") or "product",
                        revenue=self._scale_amount(self._to_float(item.get("revenue"))),
                        operating_income=self._scale_amount(self._to_float(item.get("operating_income"))),
                        confidence="medium",
                        raw_snippet="llm",
                    )
                )
            return segs
        except Exception as e:
            logger.warning(f"LLM segment extract failed: {e}")
            return []

    def _relevant_snippet(self, markdown: str, max_chars: int = 12000) -> str:
        idx = -1
        for pat in SECTION_HEADERS:
            m = re.search(pat, markdown)
            if m:
                idx = m.start()
                break
        if idx < 0:
            # 找含「营业收入」的表格附近
            m = re.search(r"\|[^\n]*营业收入[^\n]*\|", markdown)
            idx = m.start() if m else 0
        start = max(0, idx - 200)
        return markdown[start : start + max_chars]

    def _dedupe_and_clean(self, segments: List[ExtractedSegment]) -> List[ExtractedSegment]:
        seen = set()
        out: List[ExtractedSegment] = []
        for s in segments:
            key = (s.segment_name, s.segment_type)
            if key in seen:
                continue
            if self._is_skip_name(s.segment_name):
                continue
            if s.revenue is None and s.operating_income is None:
                continue
            seen.add(key)
            out.append(s)
        return out

    @staticmethod
    def _norm_header(h: str) -> str:
        return re.sub(r"\s+", "", h or "").lower()

    @staticmethod
    def _find_col(header: List[str], keys: List[str]) -> Optional[int]:
        for i, h in enumerate(header):
            for k in keys:
                if k.lower() in h or k in h:
                    return i
        return None

    @staticmethod
    def _is_skip_name(name: str) -> bool:
        n = name.strip().lower()
        if n in SKIP_NAMES:
            return True
        for s in SKIP_NAMES:
            if s in n and len(n) <= len(s) + 2:
                return True
        return False

    @staticmethod
    def _to_float(v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _parse_number(self, raw: Optional[str], is_ratio: bool = False) -> Optional[float]:
        if raw is None:
            return None
        s = str(raw).strip().replace(",", "").replace("，", "").replace("%", "")
        if not s or s in ("-", "—", "–", "N/A", "n/a"):
            return None
        mult = 1.0
        if "亿" in s:
            mult = 1e8
            s = s.replace("亿", "")
        elif "万" in s:
            mult = 1e4
            s = s.replace("万", "")
        s = re.sub(r"[^\d.\-]", "", s)
        if not s or s in (".", "-", "-."):
            return None
        try:
            val = float(s) * mult
        except ValueError:
            return None
        if is_ratio and abs(val) > 5:
            # 百分比 12.3 → 0.123
            val = val / 100.0
        return val

    @staticmethod
    def _scale_amount(val: Optional[float]) -> Optional[float]:
        """启发式：过小数字可能是亿元单位。"""
        if val is None:
            return None
        # 已带 万/亿 解析后通常 >= 1e4
        if 0 < abs(val) < 5000:
            # 可能是亿元
            return val * 1e8
        if 5000 <= abs(val) < 1e6:
            # 可能是万元
            return val * 1e4
        return val
