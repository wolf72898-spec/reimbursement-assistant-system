# -*- coding: utf-8 -*-
"""请求/响应模型（Pydantic v2）"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---- 认证 ----
class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=64)
    department: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    role: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    department: str

    class Config:
        from_attributes = True


# ---- 会话与消息 ----
class SessionOut(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    meta: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True


# ---- 报销单 ----
class ExpenseOut(BaseModel):
    id: int
    status: str
    expense_type: str
    total_amount: float
    fields: Optional[dict[str, Any]] = None
    missing_fields: Optional[list[Any]] = None

    class Config:
        from_attributes = True


class ExpenseSubmitIn(BaseModel):
    expense_type: str
    total_amount: float
    fields: dict[str, Any] = {}
