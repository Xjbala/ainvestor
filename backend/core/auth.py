# -*- coding: utf-8 -*-
"""
JWT 认证核心模块

提供 JWT Token 生成、验证和密码哈希功能。
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# ============================================================
# 配置
# ============================================================

# JWT 配置（从环境变量读取）
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# Token 模型
# ============================================================

class TokenPayload(BaseModel):
    """JWT Token 载荷"""
    sub: str  # subject (user_id)
    exp: datetime  # expiration time
    type: str  # "access" or "refresh"


class TokenData(BaseModel):
    """解析后的 Token 数据"""
    user_id: str
    token_type: str


class TokenResponse(BaseModel):
    """Token 响应（返回给客户端）"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# ============================================================
# 密码处理
# ============================================================

def hash_password(password: str) -> str:
    """
    对密码进行哈希加密

    Args:
        password: 明文密码

    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否正确

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# Token 生成与验证
# ============================================================

def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问 Token

    Args:
        user_id: 用户ID
        expires_delta: 可选的过期时间增量

    Returns:
        JWT 访问令牌
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建刷新 Token

    Args:
        user_id: 用户ID
        expires_delta: 可选的过期时间增量

    Returns:
        JWT 刷新令牌
    """
    if expires_delta is None:
        expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_token_response(user_id: str) -> TokenResponse:
    """
    创建完整的 Token 响应

    Args:
        user_id: 用户ID

    Returns:
        包含访问令牌和刷新令牌的响应
    """
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 转换为秒
    )


def decode_token(token: str) -> Optional[TokenData]:
    """
    解码并验证 Token

    Args:
        token: JWT 令牌

    Returns:
        解析后的 Token 数据，验证失败返回 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None:
            return None

        return TokenData(user_id=user_id, token_type=token_type)

    except JWTError:
        return None


def verify_access_token(token: str) -> Optional[str]:
    """
    验证访问 Token 并返回用户ID

    Args:
        token: JWT 访问令牌

    Returns:
        用户ID，验证失败返回 None
    """
    token_data = decode_token(token)

    if token_data is None:
        return None

    if token_data.token_type != "access":
        return None

    return token_data.user_id


def verify_refresh_token(token: str) -> Optional[str]:
    """
    验证刷新 Token 并返回用户ID

    Args:
        token: JWT 刷新令牌

    Returns:
        用户ID，验证失败返回 None
    """
    token_data = decode_token(token)

    if token_data is None:
        return None

    if token_data.token_type != "refresh":
        return None

    return token_data.user_id
