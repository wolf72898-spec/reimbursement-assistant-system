# -*- coding: utf-8 -*-
"""
全局配置：所有可变参数集中在环境变量，换供应商/环境不改代码。
对应架构方案的 app/core/config.py，后续可平滑迁到 pydantic-settings。
"""
import os


def _load_dotenv() -> None:
    """极简 .env 加载器（零依赖）：KEY=VALUE 逐行解析，已存在的环境变量优先"""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


class Settings:
    """系统配置项（环境变量优先级高于默认值）"""

    # ---- 应用 ----
    APP_NAME: str = "报销助手智能体系统"
    # 开发期默认 SQLite(异步)；生产用 postgresql+asyncpg://...
    DATABASE_URL: str = os.getenv("APP_DATABASE_URL", "sqlite+aiosqlite:///./dev.db")

    # ---- 认证 ----
    JWT_SECRET: str = os.getenv("APP_JWT_SECRET", "dev-secret-change-me")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("APP_JWT_EXPIRE", "720"))

    # ---- LLM 供应商（OpenAI 兼容协议，换供应商=换这三个值）----
    LLM_API_KEY: str = os.getenv("RAG_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("RAG_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MODEL: str = os.getenv("RAG_MODEL", "deepseek-chat")

    # ---- Embedding（可与对话模型不同供应商，如 DeepSeek+千问）----
    EMBED_API_KEY: str = os.getenv("EMBED_API_KEY", LLM_API_KEY)
    EMBED_BASE_URL: str = os.getenv(
        "EMBED_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "text-embedding-v3")

    # ---- RAG 参数 ----
    CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "80"))
    TOP_K: int = int(os.getenv("RAG_TOP_K", "3"))

    # ---- 存储路径 ----
    POLICY_DIR: str = os.getenv("APP_POLICY_DIR", "storage/policies")


settings = Settings()
