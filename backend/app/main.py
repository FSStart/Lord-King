"""
Nexus AI 主应用 - v2 (含 Edge TTS)
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from loguru import logger
import json
import io
import asyncio

from app.config import settings
from app.services.milvus_service import get_milvus_service
from app.services.llm_service import get_llm_service


class Services:
    milvus = None
    llm = None


services = Services()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Nexus AI 启动中...")

    try:
        services.milvus = get_milvus_service(db_path=settings.MILVUS_DB_PATH)
        logger.info("✓ Milvus 服务就绪")
    except Exception as e:
        logger.error(f"Milvus 初始化失败: {e}")

    try:
        services.llm = get_llm_service()
        logger.info("✓ LLM 服务就绪")
    except Exception as e:
        logger.error(f"LLM 初始化失败: {e}")

    logger.info("✓ Nexus AI 启动完成!")
    yield
    logger.info("Nexus AI 关闭中...")


app = FastAPI(
    title="Nexus AI",
    description="二次元语音智能助手",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return {"name": "Nexus AI", "version": "2.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "milvus": services.milvus is not None,
        "llm": services.llm is not None
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
    response = await services.llm.chat(message=request.message)
    return {"response": response}


@app.delete("/history/{user_id}")
async def clear_history(user_id: str):
    if services.milvus:
        await services.milvus.delete_user_memories(user_id)
    return {"status": "cleared", "user_id": user_id}


# ============ Edge TTS 接口 ============

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """使用 Edge TTS 生成语音"""
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
            headers={
                "Cache-Control": "no-cache",
                "Content-Disposition": "inline"
            }
        )
    except Exception as e:
        logger.error(f"TTS 生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"TTS 失败: {str(e)}")


@app.get("/tts/voices")
async def list_voices():
    """获取可用的中文声音列表"""
    try:
        import edge_tts
        voices = await edge_tts.list_voices()
        zh_voices = [v for v in voices if v["Locale"].startswith("zh-")]
        return {"voices": zh_voices}
    except Exception as e:
        return {"error": str(e)}


# ============ WebSocket ============

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

            full_response = ""
            try:
                if services.llm:
                    async for chunk in services.llm.chat_stream(message=user_message):
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

            if services.milvus:
                try:
                    await services.milvus.insert_memory(
                        user_id=user_id,
                        content=f"User: {user_message}\nAssistant: {full_response[:500]}",
                        metadata={"type": "conversation"}
                    )
                except Exception as e:
                    logger.error(f"保存记忆失败: {e}")

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(client_id)
