"""
LLM 服务 - 支持 Claude 和 Qwen
通过 .env 配置可以无缝切换
"""
from typing import List, Dict, Optional, AsyncGenerator
from loguru import logger
from app.config import settings
import json


class LLMService:
    """统一的 LLM 服务"""

    def __init__(self):
        self.use_qwen = settings.USE_QWEN and settings.QWEN_API_KEY
        self.stats = {
            "total_calls": 0,
            "haiku_calls": 0,
            "opus_calls": 0,
            "cached_hits": 0,
            "errors": 0
        }

        if self.use_qwen:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=settings.QWEN_API_KEY,
                    base_url=settings.QWEN_API_URL
                )
                self.model = settings.QWEN_MODEL
                logger.info(f"已配置 Qwen 模型: {self.model}")
            except Exception as e:
                logger.error(f"Qwen 客户端初始化失败: {e}")
                self.use_qwen = False
                self._init_claude()
        else:
            self._init_claude()

    def _init_claude(self):
        """初始化 Claude 客户端"""
        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)
            self.model = settings.CLAUDE_MODEL_HAIKU
            logger.info(f"已配置 Claude 模型: {self.model}")
        except Exception as e:
            logger.error(f"Claude 客户端初始化失败: {e}")
            self.client = None

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        system_prompt: str = "你是 Nexus AI,一个友好、专业的智能助手。"
    ) -> str:
        """简单对话"""
        try:
            self.stats["total_calls"] += 1
            messages = history or []
            messages.append({"role": "user", "content": message})

            if self.use_qwen:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                    max_tokens=2048
                )
                return response.choices[0].message.content
            else:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=messages
                )
                self.stats["haiku_calls"] += 1
                return response.content[0].text

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"LLM 调用失败: {e}")
            return f"抱歉,AI 服务暂时不可用: {str(e)[:100]}"

    async def chat_stream(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        system_prompt: str = "你是 Nexus AI,一个友好、专业的智能助手。"
    ) -> AsyncGenerator[str, None]:
        """流式对话"""
        try:
            self.stats["total_calls"] += 1
            messages = history or []
            messages.append({"role": "user", "content": message})

            if self.use_qwen:
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                    max_tokens=2048,
                    stream=True
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                async with self.client.messages.stream(
                    model=self.model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=messages
                ) as stream:
                    async for text in stream.text_stream:
                        yield text

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"流式对话失败: {e}")
            yield f"抱歉,出错了: {str(e)[:100]}"

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "provider": "Qwen" if self.use_qwen else "Claude",
            "model": self.model
        }


_llm_service = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
