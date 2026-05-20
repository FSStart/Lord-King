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
    USE_QWEN: bool = False

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
