# -*- coding: utf-8 -*-
"""
FastAPI 依赖注入

提供认证、数据库会话等依赖项，用于 API 路由。
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..persistence.db import get_db_session
from ..persistence.orm_models import User, UserRole
from ..persistence.repository import UserRepository
from .auth import verify_access_token

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
