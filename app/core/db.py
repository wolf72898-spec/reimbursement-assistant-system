# -*- coding: utf-8 -*-
"""数据库引擎与会话：SQLAlchemy 2.0 异步模式。"""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""


async def init_db() -> None:
    """
    建表（开发期用 create_all；正式版切换 Alembic 迁移管理）。
    """
    # 导入所有模型确保元数据注册完整
    from app.models import chat, expense, policy, user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
