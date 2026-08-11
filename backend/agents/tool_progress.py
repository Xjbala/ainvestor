# -*- coding: utf-8 -*-
"""Agent 工具调用的实时进度上下文。"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, Awaitable, Callable, Iterator, Optional


ToolProgressCallback = Callable[[str, str], Awaitable[None]]
_tool_progress_callback: ContextVar[Optional[ToolProgressCallback]] = ContextVar(
    "tool_progress_callback",
    default=None,
)


@contextmanager
def tool_progress_scope(callback: ToolProgressCallback) -> Iterator[None]:
    """在当前 Agent 回复链路中绑定工具进度回调。"""
    token = _tool_progress_callback.set(callback)
    try:
        yield
    finally:
        _tool_progress_callback.reset(token)


async def report_tool_progress(tool_name: str, status: str) -> None:
    """向当前 Agent 的实时回调报告工具状态。"""
    callback = _tool_progress_callback.get()
    if callback:
        await callback(tool_name, status)


def with_tool_progress(tool_function: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    """包装同步或异步工具函数，保留其名称、文档和签名。"""
    @wraps(tool_function)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        await report_tool_progress(tool_function.__name__, "started")
        try:
            result = tool_function(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            await report_tool_progress(tool_function.__name__, "failed")
            raise
        await report_tool_progress(tool_function.__name__, "completed")
        return result

    return wrapped
