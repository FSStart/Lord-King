"""
Nexus AI 主应用 - v3 (含记忆和上下文)
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from loguru import logger
import json
import io
import os
from datetime import datetime

from app.config import settings
from app.services.milvus_service import get_milvus_service
from app.services.llm_service import get_llm_service


class Services:
    milvus = None
    llm = None
    redis = None


services = Services()

# 短期记忆 - 保留最近 N 轮对话
SHORT_TERM_LIMIT = 10
# 长期记忆 - 检索 K 条相关
LONG_TERM_TOP_K = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Nexus AI 启动中...")

    try:
        services.milvus = get_milvus_service(db_path=settings.MILVUS_DB_PATH)
        logger.info("✓ Milvus 服务就绪(长期记忆)")
    except Exception as e:
        logger.error(f"Milvus 初始化失败: {e}")

    try:
        services.llm = get_llm_service()
        logger.info("✓ LLM 服务就绪")
    except Exception as e:
        logger.error(f"LLM 初始化失败: {e}")

    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        services.redis = await aioredis.from_url(redis_url, decode_responses=True)
        await services.redis.ping()
        logger.info("✓ Redis 服务就绪(短期记忆)")
    except Exception as e:
        logger.error(f"Redis 初始化失败: {e}")
        services.redis = None

    logger.info("✓ Nexus AI 启动完成!")
    yield
    logger.info("Nexus AI 关闭中...")
    if services.redis:
        await services.redis.close()


app = FastAPI(
    title="Nexus AI",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 记忆管理 ============

async def get_short_term_history(user_id: str) -> List[Dict]:
    """获取短期对话历史(Redis)"""
    if not services.redis:
        return []
    try:
        key = f"chat:history:{user_id}"
        history_json = await services.redis.lrange(key, 0, SHORT_TERM_LIMIT * 2 - 1)
        history = []
        for item in reversed(history_json):
            try:
                history.append(json.loads(item))
            except:
                continue
        return history
    except Exception as e:
        logger.error(f"获取短期记忆失败: {e}")
        return []


async def save_short_term_message(user_id: str, role: str, content: str):
    """保存消息到短期记忆"""
    if not services.redis:
        return
    try:
        key = f"chat:history:{user_id}"
        msg = json.dumps({"role": role, "content": content})
        await services.redis.lpush(key, msg)
        await services.redis.ltrim(key, 0, SHORT_TERM_LIMIT * 2 - 1)
        await services.redis.expire(key, 86400)  # 1 天过期
    except Exception as e:
        logger.error(f"保存短期记忆失败: {e}")


async def get_long_term_memories(user_id: str, query: str) -> List[str]:
    """从 Milvus 检索相关的长期记忆"""
    if not services.milvus:
        return []
    try:
        memories = await services.milvus.search_memories(
            user_id=user_id,
            query=query,
            top_k=LONG_TERM_TOP_K
        )
        return [m.get("content", "") for m in memories if m.get("content")]
    except Exception as e:
        logger.error(f"检索长期记忆失败: {e}")
        return []


async def save_long_term_memory(user_id: str, user_msg: str, ai_msg: str):
    """保存对话到长期记忆"""
    if not services.milvus:
        return
    try:
        if len(user_msg) < 5:
            return
        content = f"用户: {user_msg}\nAI: {ai_msg[:300]}"
        await services.milvus.insert_memory(
            user_id=user_id,
            content=content,
            metadata={
                "type": "conversation",
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"保存长期记忆失败: {e}")


def build_system_prompt(user_id: str, long_term_memories: List[str]) -> str:
    """构建系统提示,带上长期记忆"""
    base = """你是 Nexus AI,一个友好、专业的私人智能助手。
- 用中文回答(除非用户用英文)
- 回答简洁明了,不啰嗦
- 记住用户告诉你的信息(如姓名、爱好、习惯等)
- 如果对话历史里有相关信息,要使用它们
- 称呼用户为"主人"或者用 ta 告诉过你的名字"""

    if long_term_memories:
        memory_text = "\n".join([f"- {m}" for m in long_term_memories])
        base += f"\n\n## 你之前和这位用户的相关对话:\n{memory_text}"

    return base


# ============ WebSocket 连接管理 ============

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"客户端 {client_id} 已连接")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"客户端 {client_id} 已断开")

    async def send(self, client_id: str, data: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(data))
            except Exception as e:
                logger.error(f"发送消息失败: {e}")


manager = ConnectionManager()


# ============ 数据模型 ============

class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"


class TTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    volume: str = "+0%"


# ============ HTTP 路由 ============

@app.get("/")
async def root():
    return {"name": "Nexus AI", "version": "3.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "milvus": services.milvus is not None,
        "llm": services.llm is not None,
        "redis": services.redis is not None
    }


@app.get("/stats")
async def stats():
    return {
        "llm": services.llm.get_stats() if services.llm else {},
        "milvus": services.milvus.get_stats() if services.milvus else {}
    }


@app.get("/tools")
async def tools():
    return {"tools": [{"name": "chat", "description": "基础对话"}]}


@app.post("/chat")
async def chat(request: ChatRequest):
    if not services.llm:
        raise HTTPException(status_code=503, detail="LLM 服务未就绪")

    history = await get_short_term_history(request.user_id)
    long_term = await get_long_term_memories(request.user_id, request.message)
    system_prompt = build_system_prompt(request.user_id, long_term)

    response = await services.llm.chat(
        message=request.message,
        history=history,
        system_prompt=system_prompt
    )

    await save_short_term_message(request.user_id, "user", request.message)
    await save_short_term_message(request.user_id, "assistant", response)
    await save_long_term_memory(request.user_id, request.message, response)

    return {"response": response}


@app.delete("/history/{user_id}")
async def clear_history(user_id: str):
    if services.redis:
        try:
            await services.redis.delete(f"chat:history:{user_id}")
            logger.info(f"已清空 {user_id} 的短期记忆")
        except Exception as e:
            logger.error(f"清空短期记忆失败: {e}")

    if services.milvus:
        await services.milvus.delete_user_memories(user_id)

    return {"status": "cleared", "user_id": user_id}


@app.get("/history/{user_id}")
async def get_history(user_id: str):
    """获取用户的对话历史"""
    history = await get_short_term_history(user_id)
    return {"user_id": user_id, "history": history, "count": len(history)}


# ============ Edge TTS 接口 ============

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    try:
        import edge_tts

        communicate = edge_tts.Communicate(
            text=request.text,
            voice=request.voice,
            rate=request.rate,
            volume=request.volume
        )

        audio_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.write(chunk["data"])

        audio_data.seek(0)

        return Response(
            content=audio_data.read(),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        logger.error(f"TTS 失败: {e}")
        raise HTTPException(status_code=500, detail=f"TTS 失败: {str(e)}")


@app.get("/tts/voices")
async def list_voices():
    try:
        import edge_tts
        voices = await edge_tts.list_voices()
        zh_voices = [v for v in voices if v["Locale"].startswith("zh-")]
        return {"voices": zh_voices}
    except Exception as e:
        return {"error": str(e)}


# ============ WebSocket(主要入口) ============

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            user_id = message_data.get("user_id", client_id)

            if not user_message:
                continue

            await manager.send(client_id, {"type": "status", "status": "thinking"})

            # 加载记忆
            history = await get_short_term_history(user_id)
            long_term = await get_long_term_memories(user_id, user_message)
            system_prompt = build_system_prompt(user_id, long_term)

            logger.info(f"[{user_id}] 短期记忆: {len(history)} 条, 长期相关: {len(long_term)} 条")

            # 流式生成
            full_response = ""
            try:
                if services.llm:
                    async for chunk in services.llm.chat_stream(
                        message=user_message,
                        history=history,
                        system_prompt=system_prompt
                    ):
                        full_response += chunk
                        await manager.send(client_id, {"type": "chunk", "content": chunk})
                else:
                    full_response = "AI 服务未就绪"
                    await manager.send(client_id, {"type": "chunk", "content": full_response})
            except Exception as e:
                logger.error(f"对话出错: {e}")
                full_response = f"出错了: {str(e)[:100]}"
                await manager.send(client_id, {"type": "error", "error": str(e)})

            await manager.send(client_id, {"type": "done", "full_response": full_response})

            # 保存到记忆
            try:
                await save_short_term_message(user_id, "user", user_message)
                await save_short_term_message(user_id, "assistant", full_response)
                await save_long_term_memory(user_id, user_message, full_response)
            except Exception as e:
                logger.error(f"保存记忆失败: {e}")

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(client_id)
