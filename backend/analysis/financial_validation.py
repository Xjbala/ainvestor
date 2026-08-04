# -*- coding: utf-8 -*-
"""
财务报表完整性与勾稽校验

用于：
1. 采集断点续采：判断某公司某报表某年是否“可用完整”
2. 数据查看页：可视化核心科目覆盖率与会计勾稽结果
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


class ValidationStatus(str, Enum):
    """单期校验状态"""
    PASS = "pass"          # 核心齐全且勾稽通过
    PARTIAL = "partial"    # 有数据但核心缺失或勾稽失败
    FAIL = "fail"          # 关键核心科目缺失，不可用于分析
    EMPTY = "empty"        # 无数据


# 核心科目：分析/估值最低可用集合
# required=True 表示缺失则该期不可视为完整
CORE_SUBJECTS: Dict[str, List[Dict[str, Any]]] = {
    "BS": [
        {"code": "BSA001", "name": "货币资金", "required": True},
        {"code": "BSA020", "name": "流动资产合计", "required": False},
        {"code": "BSA121", "name": "资产总计", "required": True},
        {"code": "BSL022", "name": "流动负债合计", "required": False},
        {"code": "BSL112", "name": "负债合计", "required": True},
        {"code": "BSE010", "name": "归属于母公司所有者权益合计", "required": False},
        {"code": "BSE012", "name": "所有者权益合计", "required": True},
        {"code": "BSE001", "name": "实收资本（或股本）", "required": False},
    ],
    "IS": [
        {"code": "ISI001", "name": "营业收入", "required": True},
        {"code": "ISC001", "name": "营业成本", "required": False},
        {"code": "ISF016", "name": "营业利润", "required": True},
        {"code": "ISF019", "name": "利润总额", "required": True},
        {"code": "ISF020", "name": "所得税费用", "required": False},
        {"code": "ISF021", "name": "净利润", "required": True},
        {"code": "ISF026", "name": "归属于母公司所有者的净利润", "required": False},
        {"code": "ISE001", "name": "基本每股收益", "required": False},
    ],
    "CF": [
        {"code": "CFO020", "name": "经营活动产生的现金流量净额", "required": True},
        {"code": "CFIV012", "name": "投资活动产生的现金流量净额", "required": True},
        {"code": "CFFN011", "name": "筹资活动产生的现金流量净额", "required": True},
        {"code": "CFX001", "name": "汇率变动对现金及现金等价物的影响", "required": False},
        {"code": "CFT001", "name": "现金及现金等价物净增加额", "required": True},
        {"code": "CFT002", "name": "期初现金及现金等价物余额", "required": False},
        {"code": "CFT003", "name": "期末现金及现金等价物余额", "required": True},
    ],
}


BANK_CORE_SUBJECTS: Dict[str, List[Dict[str, Any]]] = {
    "BS": [
        {"code": "BSA023", "name": "现金及存放中央银行款项", "required": True},
        {"code": "BSA025", "name": "存放同业款项", "required": False},
        {"code": "BSA026", "name": "发放贷款及垫款净额", "required": True},
        {"code": "BSA121", "name": "资产总计", "required": True},
        {"code": "BSL025", "name": "同业存入及拆入", "required": False},
        {"code": "BSL026", "name": "客户存款", "required": True},
        {"code": "BSL112", "name": "负债合计", "required": True},
        {"code": "BSE010", "name": "归属于母公司股东权益", "required": True},
    ],
    "IS": [
        {"code": "ISI006", "name": "净利息收入", "required": True},
        {"code": "ISI007", "name": "手续费及佣金净收入", "required": False},
        {"code": "ISF016", "name": "营业利润", "required": True},
        {"code": "ISF019", "name": "利润总额", "required": True},
        {"code": "ISF020", "name": "所得税费用", "required": True},
        {"code": "ISF021", "name": "净利润", "required": True},
    ],
    "CF": [
        {"code": "CFO020", "name": "经营活动产生的现金流量净额", "required": True},
        {"code": "CFIV012", "name": "投资活动产生的现金流量净额", "required": True},
        {"code": "CFFN011", "name": "筹资活动产生的现金流量净额", "required": True},
        {"code": "CFT001", "name": "现金及现金等价物净增加额", "required": True},
        {"code": "CFT002", "name": "期初现金及现金等价物余额", "required": True},
        {"code": "CFT003", "name": "期末现金及现金等价物余额", "required": True},
    ],
}


def validation_profile_for_industry(
    industry_code: Optional[str],
    industry_name: Optional[str] = None,
    company_name: Optional[str] = None,
) -> str:
    """按行业代码、行业名称或公司名称选择财务报表验证 profile。"""
    code = str(industry_code or "").upper()
    name = str(industry_name or "")
    company = str(company_name or "")
    if code == "IND_BANK" or "BANK" in code or "银行" in name or "银行" in company:
        return "bank"
    return "default"


def core_subjects_for_profile(
    report_type: str,
    profile: str = "default",
) -> List[Dict[str, Any]]:
    """返回指定报告类型和验证 profile 的核心科目。"""
    source = BANK_CORE_SUBJECTS if profile == "bank" else CORE_SUBJECTS
    return source.get(report_type.upper(), [])


def required_core_codes(
    report_type: str,
    profile: str = "default",
) -> Set[str]:
    """返回某报表必填核心科目编码。"""
    return {
        item["code"]
        for item in core_subjects_for_profile(report_type, profile)
        if item.get("required")
    }


def all_core_codes(
    report_type: str,
    profile: str = "default",
) -> Set[str]:
    """返回某报表全部核心科目编码。"""
    return {
        item["code"]
        for item in core_subjects_for_profile(report_type, profile)
    }


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _almost_equal(
    left: Optional[float],
    right: Optional[float],
    *,
    rel_tol: float = 0.005,
    abs_tol: float = 1.0,
) -> bool:
    """
    比较两个金额是否近似相等。

    默认相对误差 0.5%，或绝对误差 1 元（适配四舍五入/单位尾差）。
    """
    if left is None or right is None:
        return False
    diff = abs(left - right)
    scale = max(abs(left), abs(right), 1.0)
    return diff <= max(abs_tol, scale * rel_tol)


def _get_first(values: Mapping[str, Optional[float]], codes: Sequence[str]) -> Optional[float]:
    for code in codes:
        if code in values and values[code] is not None:
            return values[code]
    return None


@dataclass
class SubjectCheck:
    code: str
    name: str
    required: bool
    present: bool
    value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AccountingCheck:
    key: str
    name: str
    passed: bool
    left_label: str
    left_value: Optional[float]
    right_label: str
    right_value: Optional[float]
    diff: Optional[float] = None
    message: str = ""
    severity: str = "error"  # error | warning

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PeriodValidation:
    report_type: str
    report_date: str
    status: ValidationStatus
    subject_count: int = 0
    core_total: int = 0
    core_present: int = 0
    core_required_total: int = 0
    core_required_present: int = 0
    core_hit_rate: float = 0.0
    missing_required: List[Dict[str, str]] = field(default_factory=list)
    missing_optional: List[Dict[str, str]] = field(default_factory=list)
    core_subjects: List[SubjectCheck] = field(default_factory=list)
    accounting_checks: List[AccountingCheck] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_type": self.report_type,
            "report_date": self.report_date,
            "status": self.status.value,
            "subject_count": self.subject_count,
            "core_total": self.core_total,
            "core_present": self.core_present,
            "core_required_total": self.core_required_total,
            "core_required_present": self.core_required_present,
            "core_hit_rate": self.core_hit_rate,
            "missing_required": self.missing_required,
            "missing_optional": self.missing_optional,
            "core_subjects": [c.to_dict() for c in self.core_subjects],
            "accounting_checks": [c.to_dict() for c in self.accounting_checks],
            "summary": self.summary,
        }


def build_value_map(
    items: Iterable[Mapping[str, Any]],
    *,
    code_key: str = "subject_code",
    value_key: str = "value",
) -> Dict[str, Optional[float]]:
    """将科目列表转为 code -> value 映射。"""
    result: Dict[str, Optional[float]] = {}
    for item in items:
        code = str(item.get(code_key) or "").strip()
        if not code:
            continue
        result[code] = _to_float(item.get(value_key))
    return result


def run_accounting_checks(
    report_type: str,
    values: Mapping[str, Optional[float]],
    *,
    profile: str = "default",
) -> List[AccountingCheck]:
    """执行表内勾稽校验。"""
    checks: List[AccountingCheck] = []
    rt = report_type.upper()

    if rt == "BS":
        assets = _get_first(values, ["BSA121"])
        liabilities = _get_first(values, ["BSL112"])
        equity = _get_first(values, ["BSE012"])
        equity_parent = _get_first(values, ["BSE010"])
        minority = _get_first(values, ["BSE011"])
        total_le = _get_first(values, ["BSE013"])

        # 优先：资产 = 负债 + 所有者权益合计
        if assets is not None and liabilities is not None and equity is not None:
            right = liabilities + equity
            ok = _almost_equal(assets, right)
            checks.append(
                AccountingCheck(
                    key="bs_identity",
                    name="资产负债恒等式",
                    passed=ok,
                    left_label="资产总计(BSA121)",
                    left_value=assets,
                    right_label="负债合计 + 所有者权益合计",
                    right_value=right,
                    diff=None if assets is None or right is None else assets - right,
                    message="通过" if ok else "资产总计与负债+权益不平衡",
                    severity="error",
                )
            )
        elif assets is not None and liabilities is not None and equity_parent is not None:
            # 银行通常以归属于母公司股东的权益披露；无少数股东权益时可作恒等式回退。
            right = liabilities + equity_parent + (minority or 0.0)
            ok = _almost_equal(assets, right)
            checks.append(
                AccountingCheck(
                    key="bs_identity_fallback",
                    name="资产负债恒等式(回退)",
                    passed=ok,
                    left_label="资产总计(BSA121)",
                    left_value=assets,
                    right_label="负债合计 + 归母权益 + 少数股东权益",
                    right_value=right,
                    diff=None if assets is None else assets - right,
                    message="通过" if ok else "回退恒等式不平衡",
                    severity="error",
                )
            )
        else:
            checks.append(
                AccountingCheck(
                    key="bs_identity",
                    name="资产负债恒等式",
                    passed=False,
                    left_label="资产总计(BSA121)",
                    left_value=assets,
                    right_label="负债合计 + 所有者权益合计",
                    right_value=None,
                    message="缺少恒等式所需科目，无法校验",
                    severity="error",
                )
            )

        if assets is not None and total_le is not None:
            ok = _almost_equal(assets, total_le)
            checks.append(
                AccountingCheck(
                    key="bs_total_le",
                    name="资产=负债和权益总计",
                    passed=ok,
                    left_label="资产总计(BSA121)",
                    left_value=assets,
                    right_label="负债和所有者权益总计(BSE013)",
                    right_value=total_le,
                    diff=assets - total_le,
                    message="通过" if ok else "资产总计与负债和权益总计不一致",
                    severity="warning",
                )
            )

        current_assets = _get_first(values, ["BSA020"])
        non_current_assets = _get_first(values, ["BSA120"])
        if assets is not None and current_assets is not None and non_current_assets is not None:
            right = current_assets + non_current_assets
            ok = _almost_equal(assets, right)
            checks.append(
                AccountingCheck(
                    key="bs_assets_split",
                    name="流动+非流动资产",
                    passed=ok,
                    left_label="资产总计(BSA121)",
                    left_value=assets,
                    right_label="流动资产合计 + 非流动资产合计",
                    right_value=right,
                    diff=assets - right,
                    message="通过" if ok else "资产分项合计与总计不一致",
                    severity="warning",
                )
            )

    elif rt == "IS":
        revenue_codes = ["ISI006", "ISI001", "ISI005"] if profile == "bank" else ["ISI001", "ISI005"]
        revenue = _get_first(values, revenue_codes)
        op_profit = _get_first(values, ["ISF016"])
        pretax = _get_first(values, ["ISF019"])
        tax = _get_first(values, ["ISF020"])
        net_income = _get_first(values, ["ISF021"])
        parent_ni = _get_first(values, ["ISF026"])
        minority_ni = _get_first(values, ["ISF027"])

        if pretax is not None and net_income is not None:
            # 税后净利润 ≈ 利润总额 - 所得税（所得税可能为负/缺失）
            expected = pretax - (tax or 0.0)
            ok = _almost_equal(net_income, expected, rel_tol=0.02, abs_tol=1000.0)
            checks.append(
                AccountingCheck(
                    key="is_net_income_bridge",
                    name="利润总额→净利润",
                    passed=ok,
                    left_label="净利润(ISF021)",
                    left_value=net_income,
                    right_label="利润总额 - 所得税费用",
                    right_value=expected,
                    diff=net_income - expected,
                    message="通过" if ok else "净利润与利润总额-所得税差异偏大",
                    severity="warning",
                )
            )

        if net_income is not None and parent_ni is not None:
            expected = parent_ni + (minority_ni or 0.0)
            ok = _almost_equal(net_income, expected, rel_tol=0.02, abs_tol=1000.0)
            checks.append(
                AccountingCheck(
                    key="is_ni_attribution",
                    name="净利润归属拆分",
                    passed=ok,
                    left_label="净利润(ISF021)",
                    left_value=net_income,
                    right_label="归母净利润 + 少数股东损益",
                    right_value=expected,
                    diff=net_income - expected,
                    message="通过" if ok else "净利润归属拆分不一致",
                    severity="warning",
                )
            )

        # 软检查：有收入但无净利润，或关键链路断了
        if revenue is not None and net_income is None:
            checks.append(
                AccountingCheck(
                    key="is_missing_ni",
                    name="净利润可用性",
                    passed=False,
                    left_label="营业收入",
                    left_value=revenue,
                    right_label="净利润(ISF021)",
                    right_value=None,
                    message="有营业收入但缺少净利润",
                    severity="error",
                )
            )
        if op_profit is not None and pretax is None:
            checks.append(
                AccountingCheck(
                    key="is_missing_pretax",
                    name="利润总额可用性",
                    passed=False,
                    left_label="营业利润(ISF016)",
                    left_value=op_profit,
                    right_label="利润总额(ISF019)",
                    right_value=None,
                    message="有营业利润但缺少利润总额",
                    severity="warning",
                )
            )

    elif rt == "CF":
        cfo = _get_first(values, ["CFO020"])
        cfi = _get_first(values, ["CFIV012"])
        cff = _get_first(values, ["CFFN011"])
        fx = _get_first(values, ["CFX001"])
        net_increase = _get_first(values, ["CFT001"])
        begin_cash = _get_first(values, ["CFT002"])
        end_cash = _get_first(values, ["CFT003"])

        if cfo is not None and cfi is not None and cff is not None and net_increase is not None:
            expected = cfo + cfi + cff + (fx or 0.0)
            ok = _almost_equal(net_increase, expected, rel_tol=0.01, abs_tol=1000.0)
            checks.append(
                AccountingCheck(
                    key="cf_net_increase",
                    name="三类活动→现金净增加",
                    passed=ok,
                    left_label="现金及现金等价物净增加额(CFT001)",
                    left_value=net_increase,
                    right_label="经营+投资+筹资(+汇率)",
                    right_value=expected,
                    diff=net_increase - expected,
                    message="通过" if ok else "现金净增加额与三类活动净额之和不一致",
                    severity="error",
                )
            )
        else:
            checks.append(
                AccountingCheck(
                    key="cf_net_increase",
                    name="三类活动→现金净增加",
                    passed=False,
                    left_label="现金及现金等价物净增加额(CFT001)",
                    left_value=net_increase,
                    right_label="经营+投资+筹资(+汇率)",
                    right_value=None,
                    message="缺少经营/投资/筹资净额或净增加额，无法校验",
                    severity="error",
                )
            )

        if begin_cash is not None and net_increase is not None and end_cash is not None:
            expected = begin_cash + net_increase
            ok = _almost_equal(end_cash, expected, rel_tol=0.01, abs_tol=1000.0)
            checks.append(
                AccountingCheck(
                    key="cf_cash_rollforward",
                    name="期初+净增加→期末",
                    passed=ok,
                    left_label="期末现金及现金等价物余额(CFT003)",
                    left_value=end_cash,
                    right_label="期初余额 + 净增加额",
                    right_value=expected,
                    diff=end_cash - expected,
                    message="通过" if ok else "期末现金余额勾稽失败",
                    severity="error",
                )
            )

    return checks


def validate_period(
    report_type: str,
    report_date: str,
    items: Iterable[Mapping[str, Any]],
    *,
    code_key: str = "subject_code",
    value_key: str = "value",
    profile: str = "default",
) -> PeriodValidation:
    """
    校验单个报告期的完整性与勾稽。

    items: 可迭代的科目字典，至少含 subject_code / value。
    """
    rt = report_type.upper()
    values = build_value_map(items, code_key=code_key, value_key=value_key)
    subject_count = len(values)

    core_defs = core_subjects_for_profile(rt, profile)
    core_checks: List[SubjectCheck] = []
    missing_required: List[Dict[str, str]] = []
    missing_optional: List[Dict[str, str]] = []
    present_count = 0
    required_total = 0
    required_present = 0

    for spec in core_defs:
        code = spec["code"]
        name = spec["name"]
        required = bool(spec.get("required"))
        present = code in values and values[code] is not None
        if present:
            present_count += 1
        if required:
            required_total += 1
            if present:
                required_present += 1
            else:
                missing_required.append({"code": code, "name": name})
        elif not present:
            missing_optional.append({"code": code, "name": name})

        core_checks.append(
            SubjectCheck(
                code=code,
                name=name,
                required=required,
                present=present,
                value=values.get(code),
            )
        )

    core_total = len(core_defs)
    hit_rate = (present_count / core_total) if core_total else 1.0

    if subject_count == 0:
        status = ValidationStatus.EMPTY
        accounting: List[AccountingCheck] = []
        summary = "无数据"
    else:
        accounting = run_accounting_checks(rt, values, profile=profile)
        hard_accounting_failed = any(
            (not c.passed) and c.severity == "error" for c in accounting
        )
        if required_present < required_total:
            status = ValidationStatus.FAIL
            summary = f"缺少 {required_total - required_present} 个必填核心科目"
        elif hard_accounting_failed:
            status = ValidationStatus.PARTIAL
            failed_names = [c.name for c in accounting if not c.passed and c.severity == "error"]
            summary = "核心科目齐全，但勾稽失败: " + "、".join(failed_names[:3])
        elif any(not c.passed for c in accounting) or missing_optional:
            status = ValidationStatus.PARTIAL
            summary = "可用，但存在可选科目缺失或预警级勾稽问题"
        else:
            status = ValidationStatus.PASS
            summary = "核心科目齐全，勾稽通过"

    return PeriodValidation(
        report_type=rt,
        report_date=report_date,
        status=status,
        subject_count=subject_count,
        core_total=core_total,
        core_present=present_count,
        core_required_total=required_total,
        core_required_present=required_present,
        core_hit_rate=round(hit_rate, 4),
        missing_required=missing_required,
        missing_optional=missing_optional,
        core_subjects=core_checks,
        accounting_checks=accounting,
        summary=summary,
    )


def is_year_complete_for_resume(
    present_codes: Set[str],
    report_type: str,
    profile: str = "default",
) -> bool:
    """
    断点续采判定：该年该报表是否已具备全部必填核心科目。

    仅看科目是否存在，不在此做勾稽（勾稽失败仍可避免重复全量抓取，
    由查看页/回补任务另行处理）。
    """
    required = required_core_codes(report_type, profile)
    if not required:
        return bool(present_codes)
    return required.issubset(present_codes)


def summarize_periods(period_results: Sequence[PeriodValidation]) -> Dict[str, Any]:
    """汇总多期校验结果，供 API / 前端总览。"""
    if not period_results:
        return {
            "overall_status": ValidationStatus.EMPTY.value,
            "period_count": 0,
            "pass_count": 0,
            "partial_count": 0,
            "fail_count": 0,
            "empty_count": 0,
            "avg_core_hit_rate": 0.0,
            "summary": "暂无报告期",
        }

    counts = {
        ValidationStatus.PASS.value: 0,
        ValidationStatus.PARTIAL.value: 0,
        ValidationStatus.FAIL.value: 0,
        ValidationStatus.EMPTY.value: 0,
    }
    hit_rates: List[float] = []
    for p in period_results:
        counts[p.status.value] = counts.get(p.status.value, 0) + 1
        if p.status != ValidationStatus.EMPTY:
            hit_rates.append(p.core_hit_rate)

    if counts[ValidationStatus.FAIL.value] > 0:
        overall = ValidationStatus.FAIL
    elif counts[ValidationStatus.PARTIAL.value] > 0:
        overall = ValidationStatus.PARTIAL
    elif counts[ValidationStatus.PASS.value] > 0:
        overall = ValidationStatus.PASS
    else:
        overall = ValidationStatus.EMPTY

    avg_hit = sum(hit_rates) / len(hit_rates) if hit_rates else 0.0
    summary = (
        f"{len(period_results)} 个报告期 · "
        f"通过 {counts[ValidationStatus.PASS.value]} · "
        f"部分 {counts[ValidationStatus.PARTIAL.value]} · "
        f"失败 {counts[ValidationStatus.FAIL.value]}"
    )
    return {
        "overall_status": overall.value,
        "period_count": len(period_results),
        "pass_count": counts[ValidationStatus.PASS.value],
        "partial_count": counts[ValidationStatus.PARTIAL.value],
        "fail_count": counts[ValidationStatus.FAIL.value],
        "empty_count": counts[ValidationStatus.EMPTY.value],
        "avg_core_hit_rate": round(avg_hit, 4),
        "summary": summary,
    }


def evaluate_cell_completeness(
    report_type: str,
    present_codes: Set[str],
    profile: str = "default",
) -> Dict[str, Any]:
    """
    轻量完整度评估（市场扫描用）：只看核心科目是否在库，不做勾稽。

    Returns:
        status: complete | partial | missing
        以及缺失科目列表、覆盖率
    """
    rt = report_type.upper()
    core_defs = core_subjects_for_profile(rt, profile)
    if not present_codes:
        return {
            "status": "missing",
            "core_total": len(core_defs),
            "core_present": 0,
            "core_required_total": len([c for c in core_defs if c.get("required")]),
            "core_required_present": 0,
            "core_hit_rate": 0.0,
            "missing_required": [
                {"code": c["code"], "name": c["name"]}
                for c in core_defs
                if c.get("required")
            ],
            "missing_optional": [
                {"code": c["code"], "name": c["name"]}
                for c in core_defs
                if not c.get("required")
            ],
        }

    present = 0
    required_total = 0
    required_present = 0
    missing_required: List[Dict[str, str]] = []
    missing_optional: List[Dict[str, str]] = []
    for spec in core_defs:
        code = spec["code"]
        name = spec["name"]
        required = bool(spec.get("required"))
        ok = code in present_codes
        if ok:
            present += 1
        if required:
            required_total += 1
            if ok:
                required_present += 1
            else:
                missing_required.append({"code": code, "name": name})
        elif not ok:
            missing_optional.append({"code": code, "name": name})

    total = len(core_defs) or 1
    if required_total > 0 and required_present >= required_total and not missing_optional:
        status = "complete"
    elif required_total > 0 and required_present >= required_total:
        status = "complete"  # 必填齐即可视为采集完整，可选缺失不阻断回补
    elif present == 0:
        status = "missing"
    else:
        status = "partial"

    return {
        "status": status,
        "core_total": len(core_defs),
        "core_present": present,
        "core_required_total": required_total,
        "core_required_present": required_present,
        "core_hit_rate": round(present / total, 4),
        "missing_required": missing_required,
        "missing_optional": missing_optional,
    }


def build_coverage_matrix(
    *,
    companies: Sequence[Mapping[str, Any]],
    years: Sequence[int],
    report_types: Sequence[str],
    present_index: Mapping[Tuple[str, str, int], Set[str]],
    profile_by_company: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """
    构建覆盖率矩阵。

    present_index 键: (company_code, report_type, year) -> present subject codes
    companies 项至少含 stock_code / stock_name
    """
    year_list = sorted({int(y) for y in years})
    rt_list = [rt.upper() for rt in report_types]
    company_rows: List[Dict[str, Any]] = []

    matrix_total = 0
    matrix_complete = 0
    matrix_partial = 0
    matrix_missing = 0
    by_report = {
        rt: {"complete": 0, "partial": 0, "missing": 0, "total": 0}
        for rt in rt_list
    }
    by_year = {
        str(y): {"complete": 0, "partial": 0, "missing": 0, "total": 0}
        for y in year_list
    }

    gap_companies: Set[str] = set()

    for company in companies:
        code = str(company.get("stock_code") or "")
        if not code:
            continue
        cells: List[Dict[str, Any]] = []
        company_complete = 0
        company_partial = 0
        company_missing = 0

        profile = (profile_by_company or {}).get(code, "default")
        for y in year_list:
            for rt in rt_list:
                present = present_index.get((code, rt, y), set())
                cell = evaluate_cell_completeness(rt, present, profile=profile)
                cell_row = {
                    "year": y,
                    "report_type": rt,
                    "profile": profile,
                    **cell,
                }
                cells.append(cell_row)
                matrix_total += 1
                by_report[rt]["total"] += 1
                by_year[str(y)]["total"] += 1
                st = cell["status"]
                if st == "complete":
                    matrix_complete += 1
                    company_complete += 1
                    by_report[rt]["complete"] += 1
                    by_year[str(y)]["complete"] += 1
                elif st == "partial":
                    matrix_partial += 1
                    company_partial += 1
                    by_report[rt]["partial"] += 1
                    by_year[str(y)]["partial"] += 1
                    gap_companies.add(code)
                else:
                    matrix_missing += 1
                    company_missing += 1
                    by_report[rt]["missing"] += 1
                    by_year[str(y)]["missing"] += 1
                    gap_companies.add(code)

        expected = len(year_list) * len(rt_list)
        if company_missing == expected:
            overall = "missing"
        elif company_complete == expected:
            overall = "complete"
        else:
            overall = "partial"

        company_rows.append(
            {
                "stock_code": code,
                "stock_name": company.get("stock_name") or code,
                "overall_status": overall,
                "complete_cells": company_complete,
                "partial_cells": company_partial,
                "missing_cells": company_missing,
                "expected_cells": expected,
                "coverage_rate": round(company_complete / expected, 4) if expected else 0.0,
                "cells": cells,
            }
        )

    coverage_rate = round(matrix_complete / matrix_total, 4) if matrix_total else 0.0
    return {
        "years": year_list,
        "report_types": rt_list,
        "summary": {
            "company_count": len(company_rows),
            "matrix_total": matrix_total,
            "complete_cells": matrix_complete,
            "partial_cells": matrix_partial,
            "missing_cells": matrix_missing,
            "coverage_rate": coverage_rate,
            "gap_company_count": len(gap_companies),
            "by_report_type": by_report,
            "by_year": by_year,
        },
        "gap_companies": sorted(gap_companies),
        "companies": company_rows,
    }
