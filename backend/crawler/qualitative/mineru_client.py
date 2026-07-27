# -*- coding: utf-8 -*-
"""
MinerU Online API 客户端

对接官方 v4 Precision API（需 Token）与可选 Agent API。

文档：https://mineru.net/apiManage/docs

## Precision API（推荐，年报场景）
  远程 URL：
    1. POST /api/v4/extract/task  {"url": "...", "model_version": "pipeline"}
    2. GET  /api/v4/extract/task/{task_id}  轮询 state
    3. 下载 full_zip_url，解压取 full.md

  本地文件：
    1. POST /api/v4/file-urls/batch  {"files":[{"name":"x.pdf"}], ...}
    2. PUT  file_urls[i]  上传原始字节（不要设 Content-Type）
    3. GET  /api/v4/extract-results/batch/{batch_id}  轮询
    4. 下载 full_zip_url，解压取 full.md

## 限制
  - Precision：单文件约 200MB / 200 页量级
  - Agent（免费）：体量更小，年报通常不适用
"""

from __future__ import annotations

import asyncio
import io
import logging
import zipfile
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

PRECISE_BASE_URL = "https://mineru.net/api/v4"
AGENT_BASE_URL = "https://mineru.net/api/v1/agent"

# 默认解析参数（A 股年报中文 PDF）
DEFAULT_MODEL_VERSION = "pipeline"
DEFAULT_LANGUAGE = "ch"


class MinerUClient:
    """
    MinerU PDF/文档解析客户端

    - Precision API：需 Token，支持远程 URL 与本地上传
    - Agent API：无 Token 可用，但限制严格，仅作兜底
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or "").strip() or None
        self.timeout = 300
        self._precision_client: Optional[httpx.AsyncClient] = None
        self._agent_client: Optional[httpx.AsyncClient] = None

    @property
    def has_precision_key(self) -> bool:
        return bool(self.api_key)

    @property
    def available(self) -> bool:
        return self.has_precision_key

    def _auth_headers(self) -> Dict[str, str]:
        if not self.api_key:
            return {}
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # 对外 API
    # ------------------------------------------------------------------

    async def parse_by_url(
        self,
        pdf_url: str,
        use_precision: bool = True,
        model_version: str = DEFAULT_MODEL_VERSION,
        is_ocr: bool = False,
        language: str = DEFAULT_LANGUAGE,
    ) -> dict:
        """
        解析远程 PDF URL。

        有 Token 时默认走 Precision；否则走 Agent。
        """
        if use_precision and self.has_precision_key:
            return await self._parse_url_precision(
                pdf_url,
                model_version=model_version,
                is_ocr=is_ocr,
                language=language,
            )
        return await self._parse_via_agent(pdf_url)

    async def parse_local_file(
        self,
        pdf_bytes: bytes,
        filename: str = "document.pdf",
        model_version: str = DEFAULT_MODEL_VERSION,
        is_ocr: bool = False,
        language: str = DEFAULT_LANGUAGE,
    ) -> dict:
        """
        上传本地文件并解析（Precision）。

        流程对齐官方：file-urls/batch → PUT 上传 → extract-results/batch 轮询。
        """
        if not self.has_precision_key:
            return self._empty_result(
                "本地文件上传需要 Precision API Token。请配置 MINERU_API_KEY 环境变量。"
            )
        return await self._upload_and_parse(
            pdf_bytes,
            filename=filename,
            model_version=model_version,
            is_ocr=is_ocr,
            language=language,
        )

    # ------------------------------------------------------------------
    # Precision：远程 URL
    # ------------------------------------------------------------------

    async def _parse_url_precision(
        self,
        pdf_url: str,
        model_version: str = DEFAULT_MODEL_VERSION,
        is_ocr: bool = False,
        language: str = DEFAULT_LANGUAGE,
    ) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=self._auth_headers(),
                follow_redirects=True,
            ) as client:
                body = {
                    "url": pdf_url,
                    "model_version": model_version,
                    "is_ocr": is_ocr,
                    "enable_formula": True,
                    "enable_table": True,
                    "language": language,
                }
                resp = await client.post(f"{PRECISE_BASE_URL}/extract/task", json=body)
                if resp.status_code >= 400:
                    logger.error(
                        "Precision extract/task HTTP %s: %s",
                        resp.status_code,
                        resp.text[:500],
                    )
                    return self._empty_result(
                        f"Precision API HTTP {resp.status_code}: {resp.text[:300]}"
                    )

                payload = resp.json()
                if payload.get("code") not in (0, "0", None) and payload.get("code") != 0:
                    # code==0 成功；部分实现可能无 code
                    if payload.get("code") not in (0, "0"):
                        msg = payload.get("msg") or payload.get("message") or str(payload)
                        # 若 data.task_id 仍在则继续
                        if not (payload.get("data") or {}).get("task_id"):
                            return self._empty_result(f"Precision API: {msg}")

                task_id = (payload.get("data") or {}).get("task_id") or payload.get("task_id")
                if not task_id:
                    return self._empty_result(f"Precision API 未返回 task_id: {payload}")

                result = await self._poll_precision_task(client, task_id)
                if result.get("error"):
                    return self._empty_result(result["error"])

                markdown = await self._download_markdown_from_zip(
                    client, result.get("full_zip_url")
                )
                if not markdown:
                    return self._empty_result("未能从 full_zip_url 提取 Markdown")

                return {
                    "markdown": markdown,
                    "pages": result.get("pages", 0),
                    "method": "precision",
                    "status": "success",
                    "error": None,
                    "task_id": task_id,
                }
        except Exception as e:
            logger.error(f"Precision URL parse failed: {e}", exc_info=True)
            return self._empty_result(str(e))

    async def _poll_precision_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        max_retries: int = 120,
        interval: float = 3.0,
    ) -> dict:
        """轮询 GET /api/v4/extract/task/{task_id}。"""
        for i in range(max_retries):
            try:
                resp = await client.get(f"{PRECISE_BASE_URL}/extract/task/{task_id}")
                resp.raise_for_status()
                payload = resp.json()
                data = payload.get("data") or payload
                state = (
                    data.get("state")
                    or data.get("status")
                    or payload.get("state")
                    or ""
                )
                state = str(state).lower()

                if state in ("done", "success", "completed"):
                    progress = data.get("extract_progress") or {}
                    return {
                        "full_zip_url": data.get("full_zip_url") or data.get("fullZipUrl"),
                        "pages": progress.get("total_pages")
                        or data.get("pages")
                        or 0,
                    }
                if state in ("failed", "fail", "error"):
                    return {
                        "error": data.get("err_msg")
                        or data.get("message")
                        or payload.get("msg")
                        or "解析失败",
                    }
                # pending / running / converting — continue
            except Exception as e:
                logger.debug(f"Precision poll attempt {i + 1} failed: {e}")

            await asyncio.sleep(interval)

        return {"error": "轮询超时"}

    # ------------------------------------------------------------------
    # Precision：本地上传
    # ------------------------------------------------------------------

    async def _upload_and_parse(
        self,
        pdf_bytes: bytes,
        filename: str = "document.pdf",
        model_version: str = DEFAULT_MODEL_VERSION,
        is_ocr: bool = False,
        language: str = DEFAULT_LANGUAGE,
    ) -> dict:
        """
        官方本地上传流程：
        1. POST /file-urls/batch  body={"files":[{"name":...}], ...}
        2. PUT  file_urls[0]  原始字节
        3. GET  /extract-results/batch/{batch_id}
        """
        try:
            # 上传 PUT 不能带 JSON Content-Type
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                headers = self._auth_headers()
                body = {
                    "files": [
                        {
                            "name": filename,
                            "is_ocr": is_ocr,
                            "data_id": filename,
                        }
                    ],
                    "model_version": model_version,
                    "enable_formula": True,
                    "enable_table": True,
                    "language": language,
                }
                resp = await client.post(
                    f"{PRECISE_BASE_URL}/file-urls/batch",
                    headers=headers,
                    json=body,
                )
                if resp.status_code >= 400:
                    logger.error(
                        "file-urls/batch HTTP %s: %s",
                        resp.status_code,
                        resp.text[:500],
                    )
                    return self._empty_result(
                        f"file-urls/batch HTTP {resp.status_code}: {resp.text[:300]}"
                    )

                payload = resp.json()
                if payload.get("code") not in (0, "0", None) and payload.get("code") != 0:
                    if payload.get("code") != 0:
                        msg = payload.get("msg") or str(payload)
                        if not (payload.get("data") or {}).get("file_urls"):
                            return self._empty_result(f"file-urls/batch: {msg}")

                data = payload.get("data") or {}
                batch_id = data.get("batch_id")
                file_urls = data.get("file_urls") or []
                if not batch_id or not file_urls:
                    return self._empty_result(f"未获取到 batch_id/file_urls: {payload}")

                signed_url = file_urls[0]
                # PUT 原始字节，不要设置 Content-Type（官方要求）
                put_resp = await client.put(
                    signed_url,
                    content=pdf_bytes,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )
                if put_resp.status_code >= 400:
                    logger.error(
                        "Upload PUT HTTP %s: %s",
                        put_resp.status_code,
                        put_resp.text[:300],
                    )
                    return self._empty_result(
                        f"上传失败 HTTP {put_resp.status_code}: {put_resp.text[:200]}"
                    )

                result = await self._poll_batch_result(client, batch_id)
                if result.get("error"):
                    return self._empty_result(result["error"])

                markdown = await self._download_markdown_from_zip(
                    client, result.get("full_zip_url")
                )
                if not markdown:
                    return self._empty_result("未能从 full_zip_url 提取 Markdown")

                return {
                    "markdown": markdown,
                    "pages": result.get("pages", 0),
                    "method": "precision",
                    "status": "success",
                    "error": None,
                    "batch_id": batch_id,
                }
        except Exception as e:
            logger.error(f"Upload and parse failed: {e}", exc_info=True)
            return self._empty_result(str(e))

    async def _poll_batch_result(
        self,
        client: httpx.AsyncClient,
        batch_id: str,
        max_retries: int = 120,
        interval: float = 3.0,
    ) -> dict:
        """轮询 GET /api/v4/extract-results/batch/{batch_id}。"""
        headers = self._auth_headers()
        for i in range(max_retries):
            try:
                resp = await client.get(
                    f"{PRECISE_BASE_URL}/extract-results/batch/{batch_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                payload = resp.json()
                data = payload.get("data") or payload

                # 批量结果：data.extract_result 为列表，或顶层 state
                items = (
                    data.get("extract_result")
                    or data.get("extract_results")
                    or data.get("results")
                    or []
                )
                if isinstance(items, list) and items:
                    item = items[0]
                else:
                    item = data

                state = str(
                    item.get("state") or item.get("status") or data.get("state") or ""
                ).lower()

                if state in ("done", "success", "completed"):
                    progress = item.get("extract_progress") or {}
                    return {
                        "full_zip_url": item.get("full_zip_url")
                        or item.get("fullZipUrl")
                        or data.get("full_zip_url"),
                        "pages": progress.get("total_pages") or item.get("pages") or 0,
                    }
                if state in ("failed", "fail", "error"):
                    return {
                        "error": item.get("err_msg")
                        or item.get("message")
                        or data.get("msg")
                        or "批量解析失败",
                    }
                # waiting-file / pending / running / converting
            except Exception as e:
                logger.debug(f"Batch poll attempt {i + 1} failed: {e}")

            await asyncio.sleep(interval)

        return {"error": "批量任务轮询超时"}

    async def _download_markdown_from_zip(
        self,
        client: httpx.AsyncClient,
        zip_url: Optional[str],
    ) -> str:
        """下载 full_zip_url 并提取 full.md。"""
        if not zip_url:
            return ""
        try:
            resp = await client.get(zip_url)
            resp.raise_for_status()
            content = resp.content
            # 可能直接返回 markdown
            ctype = resp.headers.get("Content-Type", "").lower()
            if "markdown" in ctype or "text/plain" in ctype:
                text = resp.text
                if text and len(text) > 50:
                    return text

            if content[:2] != b"PK":
                # 非 zip，尝试当文本
                try:
                    text = content.decode("utf-8")
                    if len(text) > 50:
                        return text
                except Exception:
                    return ""

            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                # 优先 full.md
                names = zf.namelist()
                candidates = [
                    n for n in names if n.endswith("full.md") or n.endswith("/full.md")
                ]
                if not candidates:
                    candidates = [n for n in names if n.lower().endswith(".md")]
                if not candidates:
                    logger.warning(f"ZIP has no markdown: {names[:20]}")
                    return ""
                # 选最长的 md
                best = max(candidates, key=lambda n: zf.getinfo(n).file_size)
                raw = zf.read(best)
                for enc in ("utf-8", "utf-8-sig", "gb18030"):
                    try:
                        return raw.decode(enc)
                    except Exception:
                        continue
                return raw.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Download/extract zip failed: {e}")
            return ""

    # ------------------------------------------------------------------
    # Agent API（兜底，年报通常页数超限）
    # ------------------------------------------------------------------

    async def _parse_via_agent(self, pdf_url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(
                    f"{AGENT_BASE_URL}/parse/url",
                    params={"url": pdf_url},
                )
                if resp.status_code >= 400:
                    return self._empty_result(
                        f"Agent API HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                task_data = resp.json()
                task_id = task_data.get("task_id") or task_data.get("taskId")
                if not task_id:
                    return self._empty_result(f"Agent API 未返回 task_id: {task_data}")

                result = await self._poll_agent_result(client, task_id)
                if result.get("markdown_url"):
                    md_resp = await client.get(result["markdown_url"])
                    if md_resp.status_code == 200 and md_resp.text:
                        return {
                            "markdown": md_resp.text,
                            "pages": result.get("pages", 0),
                            "method": "agent",
                            "status": "success",
                            "error": None,
                        }
                return self._empty_result(result.get("error") or "Agent 未能获取 Markdown")
        except Exception as e:
            logger.error(f"Agent API failed: {e}")
            return self._empty_result(str(e))

    async def _poll_agent_result(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        max_retries: int = 60,
        interval: float = 2.0,
    ) -> dict:
        for i in range(max_retries):
            try:
                resp = await client.get(f"{AGENT_BASE_URL}/parse/{task_id}")
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", data.get("statusCode", ""))
                if status in ("SUCCESS", "completed", "done", 1, "done"):
                    return {
                        "markdown_url": data.get("markdown_url") or data.get("markdownUrl"),
                        "pages": data.get("pages", 0),
                    }
                if status in ("FAIL", "failed", "error", -1):
                    return {"error": data.get("message", "解析失败")}
            except Exception as e:
                logger.debug(f"Agent poll attempt {i + 1} failed: {e}")
            await asyncio.sleep(interval)
        return {"error": "Agent 轮询超时"}

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result(error_msg: str) -> dict:
        return {
            "markdown": "",
            "pages": 0,
            "method": None,
            "status": "failed",
            "error": error_msg,
        }

    async def close(self):
        if self._precision_client and not self._precision_client.is_closed:
            await self._precision_client.aclose()
        if self._agent_client and not self._agent_client.is_closed:
            await self._agent_client.aclose()
