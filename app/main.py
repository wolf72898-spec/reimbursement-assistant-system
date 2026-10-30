# -*- coding: utf-8 -*-
"""应用入口：创建 FastAPI 实例、启动建表、挂载路由。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import admin, auth, chat, expenses, knowledge
from app.core.config import settings
from app.core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表（开发期 create_all，正式版切 Alembic）"""
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(expenses.router)
app.include_router(knowledge.router)
app.include_router(admin.router)


@app.get("/health", tags=["meta"])
async def health():
    """健康检查（部署探针用）"""
    return {"status": "ok", "app": settings.APP_NAME}
