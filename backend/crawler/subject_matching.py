# -*- coding: utf-8 -*-
"""新浪财务科目的确定性匹配规则。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..scripts.sina_mapping_catalog import rejected_sina_subject_mappings


_REJECTED_EXACT: Dict[str, Dict[str, str]] = rejected_sina_subject_mappings()


def normalize_subject_name(name: str) -> str:
    """仅执行不会改变会计含义的确定性文本规范化。"""
    if not name:
        return ""

    text = str(name).strip()
    text = text.translate(str.maketrans({
        "（": "(",
        "）": ")",
        "：": ":",
        "，": ",",
        "；": ";",
        "－": "-",
        "—": "-",
        "–": "-",
        "　": " ",
        "＋": "+",
    }))
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"^[0-9]+[\.、]", "", text)
    text = re.sub(r"^[（(][一二三四五六七八九十0-9]+[）)]", "", text)
    text = text.replace("加:", "").replace("减:", "").replace("其中:", "")
    # 新浪常在括号内附“损失以-号填列”等展示说明，不属于科目名称。
    text = re.sub(r"[（(][^）)]*(?:损失|亏损|转回|填列)[^）)]*[）)]", "", text)
    return text


@dataclass(frozen=True)
class SubjectMatchResult:
    """匹配成功时 subject 非空；失败时 issue_type 和 detail 说明原因。"""

    subject: Optional[Any]
    method: Optional[str] = None
    issue_type: Optional[str] = None
    detail: Optional[str] = None
    candidate_subject_codes: Tuple[str, ...] = ()

    @property
    def matched(self) -> bool:
        return self.subject is not None


def _subject_code(subject: Any) -> str:
    return str(getattr(subject, "code", ""))


def _dedupe_subjects(subjects: Iterable[Any]) -> List[Any]:
    unique: Dict[str, Any] = {}
    for subject in subjects:
        code = _subject_code(subject)
        if code:
            unique[code] = subject
    return list(unique.values())


class SinaSubjectMatcher:
    """以标准科目表为唯一目标的新浪字段匹配器。"""

    def __init__(
        self,
        subjects: Iterable[Any],
        aliases: Iterable[Any] = (),
        rejected_exact: Optional[Mapping[str, Mapping[str, str]]] = None,
    ) -> None:
        self._name_exact: Dict[str, Dict[str, List[Any]]] = {}
        self._sina_exact: Dict[str, Dict[str, List[Any]]] = {}
        self._alias_exact: Dict[str, Dict[str, List[Any]]] = {}
        self._context_alias_exact: Dict[str, Dict[Tuple[str, str], List[Any]]] = {}
        self._normalized: Dict[str, Dict[str, List[Any]]] = {}
        self._rejected_exact = {
            rt.upper(): dict(values)
            for rt, values in (rejected_exact or _REJECTED_EXACT).items()
        }

        for subject in subjects:
            report_type = self._report_type(subject)
            if not report_type:
                continue
            self._append(self._name_exact, report_type, str(subject.name).strip(), subject)
            self._append(self._normalized, report_type, normalize_subject_name(subject.name), subject)
            sina_name = str(getattr(subject, "sina_name", "") or "").strip()
            if sina_name:
                self._append(self._sina_exact, report_type, sina_name, subject)
                self._append(self._normalized, report_type, normalize_subject_name(sina_name), subject)

        for alias in aliases:
            if not bool(getattr(alias, "is_active", True)):
                continue
            if str(getattr(alias, "source", "sina")).lower() != "sina":
                continue
            subject = getattr(alias, "subject", None)
            if subject is None:
                continue
            report_type = self._report_type(alias)
            source_name = str(getattr(alias, "source_name", "") or "").strip()
            context_name = str(getattr(alias, "context_name", "") or "").strip()
            if not report_type or not source_name:
                continue
            if context_name:
                self._append_context(
                    self._context_alias_exact,
                    report_type,
                    (source_name, context_name),
                    subject,
                )
            else:
                self._append(self._alias_exact, report_type, source_name, subject)
            normalized_name = str(getattr(alias, "normalized_name", "") or "").strip()
            if not context_name:
                self._append(
                    self._normalized,
                    report_type,
                    normalized_name or normalize_subject_name(source_name),
                    subject,
                )

    @staticmethod
    def _report_type(value: Any) -> str:
        raw = getattr(value, "report_type", "")
        return str(getattr(raw, "value", raw) or "").upper()

    @staticmethod
    def _append(
        index: Dict[str, Dict[str, List[Any]]],
        report_type: str,
        key: str,
        subject: Any,
    ) -> None:
        if key:
            index.setdefault(report_type, {}).setdefault(key, []).append(subject)

    @staticmethod
    def _append_context(
        index: Dict[str, Dict[Tuple[str, str], List[Any]]],
        report_type: str,
        key: Tuple[str, str],
        subject: Any,
    ) -> None:
        index.setdefault(report_type, {}).setdefault(key, []).append(subject)

    def match(
        self,
        subject_name: str,
        report_type: str,
        context_name: str = "",
    ) -> SubjectMatchResult:
        """按上下文别名、标准名、Sina 主名、别名、归一化的顺序匹配。"""
        name = str(subject_name or "").strip()
        rt = str(report_type or "").upper()
        context = str(context_name or "").strip()
        if not name:
            return SubjectMatchResult(None, issue_type="unmatched", detail="来源科目名称为空")

        # 同名字段依赖报表层级时，先在已审核的上下文别名中精确消歧。
        if context:
            outcome = self._resolve(
                self._context_alias_exact.get(rt, {}).get((name, context), []),
                "context_alias_exact",
            )
            if outcome is not None:
                return outcome

        outcome = self._resolve(
            self._name_exact.get(rt, {}).get(name, []),
            "name_exact",
        )
        if outcome is not None:
            return outcome

        # 已审核为口径不安全的来源名称不能被遗留 sina_name 误归并。
        rejection = self._rejected_exact.get(rt, {}).get(name)
        if rejection:
            return SubjectMatchResult(None, issue_type="rejected", detail=rejection)

        for index, method in (
            (self._sina_exact, "sina_name_exact"),
            (self._alias_exact, "source_alias_exact"),
        ):
            outcome = self._resolve(index.get(rt, {}).get(name, []), method)
            if outcome is not None:
                return outcome

        normalized = normalize_subject_name(name)
        if normalized:
            outcome = self._resolve(
                self._normalized.get(rt, {}).get(normalized, []),
                "normalized_exact",
            )
            if outcome is not None:
                return outcome

        return SubjectMatchResult(None, issue_type="unmatched", detail="标准科目表无已审核映射")

    @staticmethod
    def _resolve(subjects: Sequence[Any], method: str) -> Optional[SubjectMatchResult]:
        candidates = _dedupe_subjects(subjects)
        if not candidates:
            return None
        if len(candidates) == 1:
            return SubjectMatchResult(candidates[0], method=method)
        return SubjectMatchResult(
            None,
            issue_type="ambiguous",
            detail=f"{method} 匹配到多个标准科目",
            candidate_subject_codes=tuple(sorted(_subject_code(subject) for subject in candidates)),
        )


def rejected_sina_subjects() -> Dict[str, Dict[str, str]]:
    """返回不可自动映射的新浪字段及其审核理由。"""
    return {report_type: dict(items) for report_type, items in _REJECTED_EXACT.items()}
