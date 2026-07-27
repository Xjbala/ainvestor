# -*- coding: utf-8 -*-
"""
认证 API 路由

提供用户登录、注册、登出等接口。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import (
    create_token_response,
    hash_password,
    verify_password,
    verify_refresh_token,
    TokenResponse,
)
from ..core.dependencies import get_current_user
from ..persistence.db import get_db_session
from ..persistence.orm_models import User, UserRole
from ..persistence.repository import UserRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["认证"])


# ============================================================
# 请求/响应模型
# ============================================================

class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class LoginRequest(BaseModel):
    """登录请求（JSON格式）"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class RefreshRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: str = Field(..., description="刷新令牌")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str


# ============================================================
# 认证路由
# ============================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    用户注册

    创建新用户账户并返回认证令牌。
    """
    user_repo = UserRepository(session)

    # 检查用户名是否已存在
    existing_user = await user_repo.get_by_username(request.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被使用",
        )

    # 检查邮箱是否已存在
    existing_email = await user_repo.get_by_email(request.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )

    # 创建用户
    hashed_password = hash_password(request.password)
    user = await user_repo.create(
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        role=UserRole.USER,
    )

    logger.info(f"New user registered: {user.username}")

    # 返回令牌
    return create_token_response(user.id)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    用户登录（JSON格式）

    使用用户名/邮箱和密码登录，返回认证令牌。
    """
    user_repo = UserRepository(session)

    # 尝试通过用户名查找
    user = await user_repo.get_by_username(request.username)

    # 如果用户名不存在，尝试通过邮箱查找
    if user is None:
        user = await user_repo.get_by_email(request.username)

    # 验证用户和密码
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查账户状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    logger.info(f"User logged in: {user.username}")

    return create_token_response(user.id)


@router.post("/token", response_model=TokenResponse)
async def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    """
    OAuth2 兼容登录

    使用 OAuth2 密码模式登录（用于 Swagger UI 测试）。
    """
    # 复用 JSON 登录逻辑
    request = LoginRequest(username=form_data.username, password=form_data.password)
    return await login(request, session)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    刷新令牌

    使用刷新令牌获取新的访问令牌。
    """
    user_id = verify_refresh_token(request.refresh_token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的刷新令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证用户是否仍然存在且活跃
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )

    logger.info(f"Token refreshed for user: {user.username}")

    return create_token_response(user.id)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user),
):
    """
    用户登出

    注：JWT 是无状态的，客户端需自行清除令牌。
    服务端可实现令牌黑名单（如需要）。
    """
    logger.info(f"User logged out: {current_user.username}")

    return MessageResponse(message="登出成功")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户信息

    返回已登录用户的详细信息。
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )
