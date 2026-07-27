# -*- coding: utf-8 -*-
"""
巨潮资讯网爬虫

从 cninfo.com.cn 下载上市公司年报/季报 PDF 文件。
巨潮是证监会指定的信息披露网站，所有 A 股上市公司的定期报告都在这里披露。

真实接口（与页面 disclosure/list/search 一致）：
1. 股票列表：GET /new/data/szse_stock.json（含沪深）、/new/data/bj_stock.json
2. 公告查询：POST /new/hisAnnouncement/query
   - stock 必须为「股票代码,orgId」
   - category：category_ndbg_szsh（年报）/ bndbg（中报）/ yjdbg（一季报）/ sjdbg（三季报）
3. PDF：https://static.cninfo.com.cn/{adjunctUrl}
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

CNINFO_BASE = "https://www.cninfo.com.cn"
CNINFO_PDF_BASE = "https://static.cninfo.com.cn/"
CNINFO_QUERY_URL = f"{CNINFO_BASE}/new/hisAnnouncement/query"
CNINFO_STOCK_LIST_URLS = (
    f"{CNINFO_BASE}/new/data/szse_stock.json",  # 含深市+沪市 A 股
    f"{CNINFO_BASE}/new/data/bj_stock.json",    # 北交所
)

# 定期报告分类（与页面 checkedCategory 一致）
REPORT_CATEGORY_MAP: Dict[str, str] = {
    "annual": "category_ndbg_szsh",   # 年度报告
    "semi": "category_bndbg_szsh",    # 半年度报告
    "q1": "category_yjdbg_szsh",      # 一季报
    "q3": "category_sjdbg_szsh",      # 三季报
    "quarterly": "category_yjdbg_szsh,category_sjdbg_szsh",
    "all": "category_ndbg_szsh,category_bndbg_szsh,category_yjdbg_szsh,category_sjdbg_szsh",
}

# 标题中需排除的噪声（摘要/英文版/取消/更正公告等；保留「更正后」正文）
_TITLE_EXCLUDE_RE = re.compile(
    r"(摘要|英文版|English|取消|提示性公告|上网公告|已取消|申报稿|修订说明)",
    re.IGNORECASE,
)


class CninfoCrawler:
    """
    巨潮资讯网 PDF 下载爬虫

    用于采集上市公司定期报告（年报/季报）的 PDF 原文。
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        # code -> {org_id, name, column}
        self._stock_index: Dict[str, Dict[str, str]] = {}
        self._stock_index_loaded = False
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": (
                f"{CNINFO_BASE}/new/commonUrl/pageOfSearch"
                "?url=disclosure/list/search&checkedCategory=category_ndbg_szsh"
            ),
            "Origin": CNINFO_BASE,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers=self.headers,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def search_announcements(
        self,
        stock_code: str,
        org_id: Optional[str] = None,
        year: Optional[int] = None,
        report_type: str = "all",
    ) -> list:
        """
        搜索公司定期报告公告

        Args:
            stock_code: 股票代码，如 "600519"
            org_id: 巨潮 orgId（可选，不提供则从股票列表解析）
            year: 报告所属年份（可选）
            report_type: annual / semi / q1 / q3 / quarterly / all

        Returns:
            公告列表，含 ann_id / org_id / title / ann_time / pdf_url / report_type 等
        """
        stock_code = (stock_code or "").strip()
        if not stock_code:
            return []

        client = await self._get_client()

        meta = await self._resolve_stock(client, stock_code)
        if not org_id:
            org_id = meta.get("org_id") if meta else None
        if not org_id:
            # 回退：全文搜索取 orgId
            org_id = await self._resolve_org_id_via_fulltext(client, stock_code)
        if not org_id:
            logger.warning(f"Could not resolve org_id for {stock_code}")
            return []

        column = (meta or {}).get("column") or self._infer_column(stock_code)
        categories = self._categories_for_report_type(report_type)
        se_date = self._build_se_date(year, report_type)

        all_results: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        for category in categories:
            page = 1
            page_size = 30
            while True:
                try:
                    items, total = await self._query_announcements(
                        client=client,
                        stock_code=stock_code,
                        org_id=org_id,
                        column=column,
                        category=category,
                        se_date=se_date,
                        page_num=page,
                        page_size=page_size,
                    )
                except Exception as e:
                    logger.error(
                        f"Search announcements failed for {stock_code} "
                        f"category={category} page={page}: {e}"
                    )
                    break

                if not items:
                    break

                for item in items:
                    ann_id = str(item.get("announcementId") or "")
                    title = self._clean_title(item.get("announcementTitle") or "")
                    if not title or not ann_id:
                        continue
                    if ann_id in seen_ids:
                        continue
                    if not self._is_target_report(title, report_type, year):
                        continue

                    pdf_url = self._extract_pdf_url(item)
                    if not pdf_url:
                        continue

                    seen_ids.add(ann_id)
                    all_results.append({
                        "ann_id": ann_id,
                        "org_id": item.get("orgId") or org_id,
                        "title": title,
                        "ann_time": self._format_ann_time(item.get("announcementTime")),
                        "sec_name": item.get("secName") or (meta or {}).get("name", ""),
                        "stock_code": item.get("secCode") or stock_code,
                        "pdf_url": pdf_url,
                        "report_type": self._classify_report_type(title),
                    })

                if page * page_size >= (total or 0) or len(items) < page_size:
                    break
                page += 1
                await asyncio.sleep(0.35)

        # 同类型同年份只保留主报告（优先非摘要、非英文）
        all_results = self._dedupe_prefer_main_report(all_results)
        return all_results

    async def download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """下载 PDF 文件。"""
        client = await self._get_client()
        try:
            resp = await client.get(
                pdf_url,
                headers={
                    **self.headers,
                    "Accept": "application/pdf,*/*",
                    "Referer": f"{CNINFO_BASE}/",
                },
            )
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").lower()
            body = resp.content
            if "pdf" not in content_type and not body[:5].startswith(b"%PDF"):
                logger.warning(f"Downloaded file is not PDF: {pdf_url} type={content_type}")
                return None
            return body
        except Exception as e:
            logger.error(f"Failed to download PDF {pdf_url}: {e}")
            return None

    # ------------------------------------------------------------------
    # 内部：股票 orgId / 公告查询
    # ------------------------------------------------------------------

    async def _ensure_stock_index(self, client: httpx.AsyncClient) -> None:
        if self._stock_index_loaded:
            return

        index: Dict[str, Dict[str, str]] = {}
        for url in CNINFO_STOCK_LIST_URLS:
            try:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": f"{CNINFO_BASE}/",
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"Failed to load stock list {url}: {e}")
                continue

            for item in data.get("stockList") or []:
                code = str(item.get("code") or "").strip()
                org_id = str(item.get("orgId") or "").strip()
                if not code or not org_id:
                    continue
                index[code] = {
                    "org_id": org_id,
                    "name": str(item.get("zwjc") or item.get("pinyin") or code),
                    "column": self._infer_column(code),
                }

        self._stock_index = index
        self._stock_index_loaded = True
        logger.info(f"Loaded cninfo stock index: {len(index)} codes")

    async def _resolve_stock(
        self, client: httpx.AsyncClient, stock_code: str
    ) -> Optional[Dict[str, str]]:
        await self._ensure_stock_index(client)
        return self._stock_index.get(stock_code)

    async def _resolve_org_id_via_fulltext(
        self, client: httpx.AsyncClient, stock_code: str
    ) -> Optional[str]:
        """股票列表未命中时，用全文搜索接口取 orgId。"""
        url = (
            f"{CNINFO_BASE}/new/fulltextSearch/full"
            f"?searchkey={stock_code}&sdate=&edate=&isfulltext=false"
            f"&sortName=pubdate&sortType=desc&pageNum=1&pageSize=1"
        )
        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": f"{CNINFO_BASE}/",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("announcements") or data.get("result") or []
            if items:
                org_id = items[0].get("orgId")
                if org_id:
                    self._stock_index[stock_code] = {
                        "org_id": org_id,
                        "name": items[0].get("secName") or stock_code,
                        "column": self._infer_column(stock_code),
                    }
                    return org_id
        except Exception as e:
            logger.debug(f"fulltext org_id resolve failed for {stock_code}: {e}")
        return None

    async def _query_announcements(
        self,
        client: httpx.AsyncClient,
        stock_code: str,
        org_id: str,
        column: str,
        category: str,
        se_date: str,
        page_num: int,
        page_size: int,
    ) -> tuple[list, int]:
        """POST hisAnnouncement/query，返回 (items, total)。"""
        form = {
            "pageNum": str(page_num),
            "pageSize": str(page_size),
            "column": column,
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{stock_code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": category,
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        resp = await client.post(CNINFO_QUERY_URL, data=form)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("announcements") or []
        total = int(
            data.get("totalAnnouncement")
            or data.get("totalRecordNum")
            or len(items)
        )
        return items, total

    # ------------------------------------------------------------------
    # 过滤 / 分类 / 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_column(stock_code: str) -> str:
        """根据股票代码推断巨潮 column：szse / sse / bj。"""
        code = (stock_code or "").strip()
        if code.startswith(("0", "1", "2", "3")):
            return "szse"
        if code.startswith(("4", "8", "9")):
            return "bj"
        # 5/6/7 等沪市
        return "sse"

    @staticmethod
    def _categories_for_report_type(report_type: str) -> List[str]:
        key = (report_type or "all").lower()
        raw = REPORT_CATEGORY_MAP.get(key, REPORT_CATEGORY_MAP["all"])
        return [c.strip() for c in raw.split(",") if c.strip()]

    @staticmethod
    def _build_se_date(year: Optional[int], report_type: str) -> str:
        """
        构造 seDate=start~end。

        年报通常在次年披露，故 year=Y 的年报查询窗口取 Y-01-01 ~ Y+2-06-30。
        """
        today = date.today()
        if not year:
            # 默认近 10 年
            start = f"{today.year - 10}-01-01"
            end = today.strftime("%Y-%m-%d")
            return f"{start}~{end}"

        rt = (report_type or "all").lower()
        if rt == "annual":
            start = f"{year}-12-01"
            end = f"{year + 2}-06-30"
        elif rt == "semi":
            start = f"{year}-06-01"
            end = f"{year + 1}-06-30"
        elif rt in ("q1", "quarterly"):
            start = f"{year}-01-01"
            end = f"{year + 1}-06-30"
        elif rt == "q3":
            start = f"{year}-07-01"
            end = f"{year + 1}-06-30"
        else:
            start = f"{year}-01-01"
            end = f"{year + 2}-06-30"

        # 不晚于今天
        end_date = min(date.fromisoformat(end), today)
        return f"{start}~{end_date.isoformat()}"

    @staticmethod
    def _clean_title(title: str) -> str:
        return re.sub(r"</?em>", "", title or "").strip()

    def _is_target_report(
        self, title: str, report_type: str, year: Optional[int]
    ) -> bool:
        """是否为目标定期报告正文。"""
        if _TITLE_EXCLUDE_RE.search(title):
            return False

        rt = (report_type or "all").lower()
        classified = self._classify_report_type(title)

        type_ok = {
            "annual": classified == "annual",
            "semi": classified == "semi",
            "q1": classified == "q1",
            "q3": classified == "q3",
            "quarterly": classified in ("q1", "q3", "quarterly"),
            "all": classified in ("annual", "semi", "q1", "q3", "quarterly"),
        }.get(rt, True)
        if not type_ok:
            return False

        if year is not None:
            # 标题里出现了其他年份且不含目标年 → 丢弃
            years_in_title = re.findall(r"20\d{2}", title)
            if years_in_title and str(year) not in years_in_title:
                return False
        return True

    @staticmethod
    def _extract_pdf_url(item: dict) -> Optional[str]:
        adjunct_url = (item.get("adjunctUrl") or "").strip()
        if not adjunct_url:
            return None
        lower = adjunct_url.lower()
        if not (lower.endswith(".pdf") or "finalpage" in lower):
            return None
        if adjunct_url.startswith("http"):
            return adjunct_url
        return CNINFO_PDF_BASE + adjunct_url.lstrip("/")

    @staticmethod
    def _format_ann_time(value: Any) -> str:
        """announcementTime 可能是毫秒时间戳或字符串。"""
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            try:
                ts = int(value) / 1000 if int(value) > 10_000_000_000 else int(value)
                return datetime.fromtimestamp(ts).date().isoformat()
            except Exception:
                return str(value)
        return str(value)

    @staticmethod
    def _classify_report_type(title: str) -> str:
        """根据标题分类报告类型。"""
        t = title or ""
        # 注意顺序：半年度/季度优先于“年度”
        if "半年度" in t or "中期报告" in t or "中报" in t:
            return "semi"
        if "第一季度" in t or "一季度" in t or "一季报" in t:
            return "q1"
        if "第三季度" in t or "三季度" in t or "三季报" in t:
            return "q3"
        if "第二季度" in t or "二季度" in t or "第四季度" in t or "四季度" in t:
            return "quarterly"
        if "年度报告" in t or "年报" in t:
            return "annual"
        if "季度报告" in t:
            return "quarterly"
        return "unknown"

    def _dedupe_prefer_main_report(
        self, items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        同一股票 + 报告类型 + 标题年份 只保留一条主报告。
        优先：不含摘要/英文，标题更短（通常是正式年报）。
        """
        buckets: Dict[str, Dict[str, Any]] = {}
        for item in items:
            title = item.get("title") or ""
            year_m = re.search(r"(20\d{2})\s*年", title)
            year_key = year_m.group(1) if year_m else item.get("ann_time", "")[:4]
            key = f"{item.get('stock_code')}|{item.get('report_type')}|{year_key}"
            prev = buckets.get(key)
            if prev is None or self._report_priority(item) > self._report_priority(prev):
                buckets[key] = item
        # 按披露时间倒序
        result = list(buckets.values())
        result.sort(key=lambda x: x.get("ann_time") or "", reverse=True)
        return result

    @staticmethod
    def _report_priority(item: Dict[str, Any]) -> tuple:
        title = item.get("title") or ""
        score = 0
        if "摘要" not in title:
            score += 10
        if "英文" not in title and "English" not in title:
            score += 5
        if "更正后" in title:
            score += 2  # 更正后正文优于旧版
        # 标题越短通常越接近正式报告名
        score += max(0, 40 - len(title)) // 10
        return (score, item.get("ann_time") or "")
