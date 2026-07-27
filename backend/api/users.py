# -*- coding: utf-8 -*-
"""
用户管理 API 路由

提供用户列表、角色管理等管理功能。
仅管理员可访问。
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, require_admin, require_superadmin
from ..persistence.db import get_db_session
from ..persistence.orm_models import User, UserRole
from ..persistence.repository import UserRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["用户管理"])


# ============================================================
# 请求/响应模型
# ============================================================

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


class UserListResponse(BaseModel):
    """用户列表响应"""
    users: List[UserResponse]
    total: int
    skip: int
    limit: int


class UpdateUserRoleRequest(BaseModel):
    """更新用户角色请求"""
    role: str = Field(..., description="新角色: user, expert, admin, superadmin")


class UpdateUserStatusRequest(BaseModel):
    """更新用户状态请求"""
    is_active: bool = Field(..., description="是否激活")


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str


# ============================================================
# 用户管理路由
# ============================================================

@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    """
    获取用户列表

    仅管理员可访问。支持分页。
    """
    user_repo = UserRepository(session)
    users = await user_repo.get_all(skip=skip, limit=limit)

    user_responses = [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
        )
        for user in users
    ]

    return UserListResponse(
        users=user_responses,
        total=len(user_responses),  # TODO: 实现真正的总数查询
        skip=skip,
        limit=limit,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    """
    获取指定用户信息

    仅管理员可访问。
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    """
    更新用户角色

    - 管理员可将用户设为: user, expert
    - 仅超级管理员可设置: admin, superadmin
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 验证角色值
    try:
        new_role = UserRole(request.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色值: {request.role}",
        )

    # 只有超级管理员可以设置 admin 或 superadmin 角色
    if new_role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        if current_user.role != UserRole.SUPERADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有超级管理员可以授予管理员权限",
            )

    # 不能修改自己的角色
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的角色",
        )

    # 更新角色
    user.role = new_role
    await session.commit()

    logger.info(f"User {user.username} role updated to {new_role.value} by {current_user.username}")

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    request: UpdateUserStatusRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    """
    更新用户状态（激活/禁用）

    仅管理员可访问。不能禁用自己。
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不能禁用自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用自己的账户",
        )

    # 不能对超级管理员进行操作（除非自己也是超级管理员）
    if user.role == UserRole.SUPERADMIN and current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能修改超级管理员的状态",
        )

    user.is_active = request.is_active
    await session.commit()

    action = "激活" if request.is_active else "禁用"
    logger.info(f"User {user.username} {action} by {current_user.username}")

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_superadmin),
):
    """
    删除用户

    仅超级管理员可访问。不能删除自己。
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户",
        )

    username = user.username
    await session.delete(user)
    await session.commit()

    logger.warning(f"User {username} deleted by {current_user.username}")

    return MessageResponse(message=f"用户 {username} 已删除")
