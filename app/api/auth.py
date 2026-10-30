# -*- coding: utf-8 -*-
"""认证路由：注册 / 登录 / 当前用户信息。首个注册用户自动成为管理员。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.core.security import create_token, hash_password, verify_password
from app.models.user import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    """注册；系统无任何用户时，第一个注册者自动成为 admin"""
    exists = await db.scalar(
        select(func.count()).select_from(User).where(User.username == body.username)
    )
    if exists:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名已存在")
    count = await db.scalar(select(func.count()).select_from(User))
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        # 首个用户 = 管理员（种子账号机制，正式版改为命令行创建）
        role="admin" if not count else "employee",
        department=body.department,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)):
    """用户名密码登录，签发 JWT"""
    user = await db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    return TokenOut(access_token=create_token(user.id, user.role), role=user.role)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """返回当前登录用户信息（前端登录后调用）"""
    return current_user
