# -*- coding: utf-8 -*-
"""
邮件发送服务

优先使用 Resend API；未配置 RESEND_API_KEY 时降级为日志打印（开发环境）。
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
_RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
_FROM_EMAIL = os.getenv("MAIL_FROM", "Ainvestor <noreply@ainvestor.dev>")
_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Ainvestor")


def is_email_service_configured() -> bool:
    return bool(_RESEND_API_KEY)


async def send_verification_code_email(to_email: str, code: str) -> None:
    """发送验证码邮件"""
    subject = "【Ainvestor】邮箱验证码"
    html = _build_verification_email_html(code)

    if not _RESEND_API_KEY:
        logger.info(
            "[邮件服务未配置] 验证码已生成但未发送 — 收件人=%s 验证码=%s",
            to_email,
            code,
        )
        return

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {_RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": _FROM_EMAIL,
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                },
            )
            if resp.status_code >= 400:
                logger.error(
                    "Resend 发送失败 status=%s body=%s",
                    resp.status_code,
                    resp.text,
                )
                raise RuntimeError(f"邮件发送失败: {resp.status_code}")
            logger.info("验证码邮件已发送至 %s", to_email)
    except Exception:
        logger.exception("发送验证码邮件异常 to=%s", to_email)
        raise


def _build_verification_email_html(code: str) -> str:
    return f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
  <h2 style="color: #1a1a1a; margin: 0 0 16px;">邮箱验证码</h2>
  <p style="color: #555; font-size: 14px; line-height: 1.6;">你正在注册 Ainvestor 账号，请使用以下验证码完成验证：</p>
  <div style="margin: 24px 0; text-align: center;">
    <span style="display: inline-block; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #b8860b; background: #faf6ed; padding: 16px 32px; border-radius: 8px;">{code}</span>
  </div>
  <p style="color: #999; font-size: 12px; line-height: 1.6;">验证码 10 分钟内有效。如果不是你本人操作，请忽略此邮件。</p>
</div>
"""
