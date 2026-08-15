# -*- coding: utf-8 -*-
"""
FastAPI 依赖注入

提供认证、数据库会话等依赖项，用于 API 路由。
"""

import logging
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.db import get_db_session
from ..persistence.orm_models import User, UserRole
from ..persistence.repository import UserRepository
from .auth import verify_access_token
from .quota import (
    ANON_COOKIE_NAME,
    Identity,
    generate_anonymous_key,
    hash_anonymous_key,
    hash_ip,
)

logger = logging.getLogger(__name__)

# OAuth2 密码bearer模式
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ============================================================
# 用户认证依赖
# ============================================================

async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """
    获取当前用户（可选）

    如果没有提供 Token 或 Token 无效，返回 None。
    适用于允许匿名访问的接口。
    """
    if token is None:
        return None

    user_id = verify_access_token(token)
    if user_id is None:
        return None

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if user is None or not user.is_active:
        return None

    return user


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    获取当前用户（必须）

    如果没有提供 Token 或 Token 无效，抛出 401 异常。
    适用于需要登录的接口。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    user_id = verify_access_token(token)
    if user_id is None:
        raise credentials_exception

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前活跃用户

    快捷依赖，等同于 get_current_user。
    """
    return current_user


# ============================================================
# 权限检查依赖
# ============================================================

def require_role(*roles: UserRole):
    """
    创建角色检查依赖

    用法:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_endpoint():
            ...

    Args:
        *roles: 允许的角色列表

    Returns:
        依赖函数
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return current_user

    return role_checker


async def require_expert(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    要求专家用户权限

    允许: EXPERT, ADMIN, SUPERADMIN
    """
    allowed_roles = {UserRole.EXPERT, UserRole.ADMIN, UserRole.SUPERADMIN}
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要专家用户权限",
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    要求管理员权限

    允许: ADMIN, SUPERADMIN
    """
    allowed_roles = {UserRole.ADMIN, UserRole.SUPERADMIN}
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


async def require_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    要求超级管理员权限

    仅允许: SUPERADMIN
    """
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限",
        )
    return current_user


# ============================================================
# 匿名身份与配额
# ============================================================

def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def get_anonymous_or_user(
    request: Request,
    response: Response,
    token: Optional[str] = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> Tuple[Identity, Optional[User]]:
    """返回 (Identity, User|None)。

    优先解析 JWT，未提供或失效则回退到匿名 cookie。
    cookie 不存在时生成新 UUID 并 Set-Cookie（HttpOnly, SameSite=Lax, 7天）。
    匿名 cookie 值在落库前先 hash，避免明文关联。
    """
    if token:
        user_id = verify_access_token(token)
        if user_id:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(user_id)
            if user and user.is_active:
                return Identity(
                    user_id=user.id,
                    anonymous_key=None,
                    ip_hash=hash_ip(_client_ip(request)),
                ), user

    # 匿名路径
    raw_cookie = request.cookies.get(ANON_COOKIE_NAME)
    if raw_cookie:
        anon_key = hash_anonymous_key(raw_cookie)
    else:
        raw_cookie = generate_anonymous_key()
        anon_key = hash_anonymous_key(raw_cookie)
        response.set_cookie(
            key=ANON_COOKIE_NAME,
            value=raw_cookie,
            max_age=60 * 60 * 24 * 7,  # 7 天
            httponly=True,
            samesite="lax",
            secure=False,  # 生产环境通过反向代理上 HTTPS 后改为 True
        )

    return Identity(
        user_id=None,
        anonymous_key=anon_key,
        ip_hash=hash_ip(_client_ip(request)),
    ), None


async def get_identity(
    identity_user: Tuple[Identity, Optional[User]] = Depends(get_anonymous_or_user),
) -> Identity:
    """只取 Identity（用于只需配额闸门、不需要 user 对象的路由）。"""
    return identity_user[0]


def consume_quota(resource):
    """配额守卫依赖工厂。

    用法:
        @router.get("/foo", dependencies=[Depends(consume_quota(QuotaResource.EXPERT_VALUATION))])
        async def foo(...):
            ...
    """
    from ..persistence.orm_models import QuotaResource as _QR
    res = _QR(resource) if isinstance(resource, str) else resource

    async def _guard(
        identity: Identity = Depends(get_identity),
        session: AsyncSession = Depends(get_db_session),
    ) -> Identity:
        from .quota import check_and_consume
        await check_and_consume(session, identity, res)
        # get_db_session 会自动 commit，usage_event 落库
        return identity

    return _guard
