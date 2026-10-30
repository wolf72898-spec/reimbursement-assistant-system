# -*- coding: utf-8 -*-
"""应用入口：创建 FastAPI 实例、启动建表、挂载路由。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.agent.loop import seed_prompts
from app.api import admin, auth, chat, construction, expenses, knowledge
from app.core.config import settings
from app.core.db import init_db
from app.core.seed_change import seed_changes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表（开发期 create_all，正式版切 Alembic）+ 播种提示词模板与演示数据"""
    await init_db()
    from app.core.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await seed_prompts(db)
        await seed_changes(db)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(construction.router)
app.include_router(chat.router)
app.include_router(expenses.router)
app.include_router(knowledge.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
async def root():
    """根路径返回中文聊天界面（员工与管理员共用）"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health", tags=["meta"])
async def health():
    """健康检查（部署探针用）"""
    return {"status": "ok", "app": settings.APP_NAME}
