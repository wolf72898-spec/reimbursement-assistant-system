# -*- coding: utf-8 -*-
"""FastAPI 依赖注入：数据库会话、当前用户、管理员鉴权。"""
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """每个请求一个独立数据库会话，用完即关"""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """解析 Bearer Token → 加载用户；未登录返回 401"""
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    payload = decode_token(cred.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已禁用")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """管理员专用依赖，非 admin 返回 403"""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user
