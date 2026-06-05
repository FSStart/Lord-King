"""
应用配置
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # API Keys
    CLAUDE_API_KEY: str = "sk-ant-placeholder"
    QWEN_API_KEY: Optional[str] = None
    QWEN_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-max-latest"
    # 视觉(多模态)模型 —— 用户发图片时切到这个模型. DashScope 兼容接口可用 qwen-vl-max-latest
    QWEN_VL_MODEL: str = "qwen-vl-max-latest"
    USE_QWEN: bool = False

    # 嵌入(向量)模型 —— 用于长期记忆的真实语义检索. DashScope 兼容接口提供 text-embedding-v3
    EMBED_MODEL: str = "text-embedding-v3"
    EMBED_DIM: int = 1024

    # 数据库
    POSTGRES_PASSWORD: str = "MyNexus2026"
    DATABASE_URL: str = "postgresql+asyncpg://ai_user:MyNexus2026@postgres:5432/ai_assistant"

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # Milvus
    MILVUS_DB_PATH: str = "/app/data/milvus_lite.db"

    # 应用
    DEBUG: bool = False
    APP_NAME: str = "Nexus AI"

    # 模型配置
    CLAUDE_MODEL_OPUS: str = "claude-opus-4-5"
    CLAUDE_MODEL_HAIKU: str = "claude-haiku-4-5"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
