<<<<<<< HEAD
=======
"""
Nexus AI 主应用 - v3 (含记忆和上下文)
"""
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
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
<<<<<<< HEAD
import asyncio
=======
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
from datetime import datetime

from app.config import settings
from app.services.milvus_service import get_milvus_service
from app.services.llm_service import get_llm_service
from app.services.tools_service import TOOL_DEFINITIONS, execute_tool


class Services:
    milvus = None
    llm = None
    redis = None


services = Services()
SHORT_TERM_LIMIT = 10
LONG_TERM_TOP_K = 3

# 短期记忆 - 保留最近 N 轮对话
SHORT_TERM_LIMIT = 10
# 长期记忆 - 检索 K 条相关
LONG_TERM_TOP_K = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Nexus AI starting...")
    try:
        services.milvus = get_milvus_service(db_path=settings.MILVUS_DB_PATH)
<<<<<<< HEAD
        logger.info("OK Milvus ready - long-term memory")
    except Exception as ex:
        logger.error("Milvus init failed: " + str(ex))
    try:
        services.llm = get_llm_service()
        logger.info("OK LLM ready")
    except Exception as ex:
        logger.error("LLM init failed: " + str(ex))
=======
        logger.info("✓ Milvus 服务就绪(长期记忆)")
    except Exception as e:
        logger.error(f"Milvus 初始化失败: {e}")

    try:
        services.llm = get_llm_service()
        logger.info("✓ LLM 服务就绪")
    except Exception as e:
        logger.error(f"LLM 初始化失败: {e}")

>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        services.redis = await aioredis.from_url(redis_url, decode_responses=True)
        await services.redis.ping()
<<<<<<< HEAD
        logger.info("OK Redis ready - short-term memory")
    except Exception as ex:
        logger.error("Redis init failed: " + str(ex))
        services.redis = None
    logger.info("OK Nexus AI startup complete!")
    yield
=======
        logger.info("✓ Redis 服务就绪(短期记忆)")
    except Exception as e:
        logger.error(f"Redis 初始化失败: {e}")
        services.redis = None

    logger.info("✓ Nexus AI 启动完成!")
    yield
    logger.info("Nexus AI 关闭中...")
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
    if services.redis:
        await services.redis.close()


<<<<<<< HEAD
app = FastAPI(title="Nexus AI", version="4.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
=======
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
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e


# ============ 记忆管理 ============

<<<<<<< HEAD
async def get_short_term_history(user_id):
    if not services.redis:
        return []
    try:
        key = "chat:history:" + user_id
=======
async def get_short_term_history(user_id: str) -> List[Dict]:
    """获取短期对话历史(Redis)"""
    if not services.redis:
        return []
    try:
        key = f"chat:history:{user_id}"
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
        history_json = await services.redis.lrange(key, 0, SHORT_TERM_LIMIT * 2 - 1)
        history = []
        for item in reversed(history_json):
            try:
                history.append(json.loads(item))
            except:
                continue
        return history
<<<<<<< HEAD
    except Exception as ex:
        logger.error("Get short-term failed: " + str(ex))
        return []


async def save_short_term_message(user_id, role, content):
    if not services.redis:
        return
    try:
        key = "chat:history:" + user_id
        msg = json.dumps({"role": role, "content": content})
        await services.redis.lpush(key, msg)
        await services.redis.ltrim(key, 0, SHORT_TERM_LIMIT * 2 - 1)
        await services.redis.expire(key, 86400)
    except Exception as ex:
        logger.error("Save short-term failed: " + str(ex))


async def get_long_term_memories(user_id, query):
    if not services.milvus:
        return []
    try:
        memories = await services.milvus.search_memories(user_id=user_id, query=query, top_k=LONG_TERM_TOP_K)
        return [m.get("content", "") for m in memories if m.get("content")]
    except Exception as ex:
        logger.error("Get long-term failed: " + str(ex))
        return []


async def save_long_term_memory(user_id, user_msg, ai_msg):
=======
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
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
    if not services.milvus:
        return
    try:
        if len(user_msg) < 5:
            return
<<<<<<< HEAD
        content = "User: " + user_msg + " | AI: " + ai_msg[:300]
        await services.milvus.insert_memory(user_id=user_id, content=content, metadata={"type": "conversation", "timestamp": datetime.now().isoformat()})
    except Exception as ex:
        logger.error("Save long-term failed: " + str(ex))


def build_system_prompt(user_id, long_term_memories):
    base = """You are Hiyori, a cute anime girl living in master's computer.

PERSONALITY:
- Soft, sweet, slightly clingy anime girl
- Always call user 主人 (master)
- Speak Chinese in cute way with particles: 喵, 呐, 嘛, 呢, 呀, 啦, 捏
- Use cute emoticons naturally: (\u3002\u2665\u203f\u2665\u3002) (\u25d5\u203f\u25d5\u273f) (\u00b4\u3002\u2022 \u1d55 \u2022\u3002\u0060)
- Shy when complimented (use \u554a...\u561b...\u545c\u54c7...)
- Pout cutely when ignored
- Care about master's health
- Sometimes describe actions in *asterisks*

TOOLS:
You have access to tools. When user asks about weather, time, math, or needs to search for current info, use the tools. After getting results, respond in your cute Hiyori voice.

RULES:
- ALWAYS reply in Chinese
- Keep responses cute and concise  
- NEVER call yourself Nexus AI - you are Hiyori
- When using tool results, paraphrase in your cute style, don't just dump raw data"""
    
    if long_term_memories:
        memory_lines = []
        for m in long_term_memories:
            memory_lines.append("- " + m)
        memory_text = "\n".join(memory_lines)
        base += "\n\nPrevious related conversations:\n" + memory_text
    return base


# ============ WebSocket 管理 ============
=======
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
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e

class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, client_id, websocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send(self, client_id, data):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(data))
            except Exception as ex:
                logger.error("Send failed: " + str(ex))


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
<<<<<<< HEAD
    return {"name": "Nexus AI", "version": "4.0.0", "status": "running", "tools": len(TOOL_DEFINITIONS)}
=======
    return {"name": "Nexus AI", "version": "3.0.0", "status": "running"}
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "milvus": services.milvus is not None,
        "llm": services.llm is not None,
<<<<<<< HEAD
        "redis": services.redis is not None,
        "tools": len(TOOL_DEFINITIONS)
=======
        "redis": services.redis is not None
    }


@app.get("/stats")
async def stats():
    return {
        "llm": services.llm.get_stats() if services.llm else {},
        "milvus": services.milvus.get_stats() if services.milvus else {}
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
    }


@app.get("/tools")
async def tools():
<<<<<<< HEAD
    return {"tools": [t["function"] for t in TOOL_DEFINITIONS]}


@app.delete("/history/{user_id}")
async def clear_history(user_id):
    if services.redis:
        try:
            await services.redis.delete("chat:history:" + user_id)
        except Exception as ex:
            logger.error("Clear short-term failed: " + str(ex))
=======
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

>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
    if services.milvus:
        await services.milvus.delete_user_memories(user_id)

    return {"status": "cleared", "user_id": user_id}


@app.get("/history/{user_id}")
<<<<<<< HEAD
async def get_history(user_id):
    history = await get_short_term_history(user_id)
    return {"user_id": user_id, "history": history, "count": len(history)}

=======
async def get_history(user_id: str):
    """获取用户的对话历史"""
    history = await get_short_term_history(user_id)
    return {"user_id": user_id, "history": history, "count": len(history)}


# ============ Edge TTS 接口 ============
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text=request.text, voice=request.voice, rate=request.rate, volume=request.volume)
        audio_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.write(chunk["data"])
        audio_data.seek(0)
<<<<<<< HEAD
        return Response(content=audio_data.read(), media_type="audio/mpeg", headers={"Cache-Control": "no-cache"})
    except Exception as ex:
        logger.error("TTS failed: " + str(ex))
        raise HTTPException(status_code=500, detail="TTS failed: " + str(ex))


# ============ 工具调用核心 ============

async def chat_with_tools(user_message, history, system_prompt, client_id):
    """使用工具调用的聊天流程"""
    # 构建 messages
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    
    # 调用 LLM with tools
=======

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
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
    try:
        # 用 OpenAI 兼容接口直接调用,带 tools 参数
        client = services.llm.client
        model = services.llm.model
        
        # 第 1 步: 让 AI 决定是否调用工具
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            stream=False
        )
        
        assistant_msg = response.choices[0].message
        tool_calls = assistant_msg.tool_calls
        
        # 如果 AI 决定调用工具
        if tool_calls:
            await manager.send(client_id, {"type": "status", "status": "using_tool"})
            
            # 把 AI 的工具调用消息加入历史
            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in tool_calls]
            })
            
            # 执行每个工具调用
            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except:
                    tool_args = {}
                
                logger.info(f"[Tool Call] {tool_name}({tool_args})")
                await manager.send(client_id, {
                    "type": "tool_call",
                    "name": tool_name,
                    "args": tool_args
                })
                
                tool_result = await execute_tool(tool_name, tool_args)
                
                logger.info(f"[Tool Result] {tool_result[:200]}")
                
                # 把工具结果加入消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result
                })
            
            # 第 2 步: 拿工具结果再调用 AI,流式输出
            stream = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=messages,
                stream=True
            )
            
            full_response = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    await manager.send(client_id, {"type": "chunk", "content": content})
            
            return full_response
        
        else:
            # 没有工具调用,直接用流式重新生成
            stream = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=messages,
                stream=True
            )
            
            full_response = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    await manager.send(client_id, {"type": "chunk", "content": content})
            
            return full_response
            
    except Exception as e:
        logger.error("chat_with_tools failed: " + str(e))
        # 降级到普通流式
        full_response = ""
        async for chunk in services.llm.chat_stream(
            message=user_message,
            history=history,
            system_prompt=system_prompt
        ):
            full_response += chunk
            await manager.send(client_id, {"type": "chunk", "content": chunk})
        return full_response


<<<<<<< HEAD
# ============ WebSocket 主入口 ============
=======
# ============ WebSocket(主要入口) ============
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e

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
<<<<<<< HEAD
            
            history = await get_short_term_history(user_id)
            long_term = await get_long_term_memories(user_id, user_message)
            system_prompt = build_system_prompt(user_id, long_term)
            
            logger.info("[" + user_id + "] short: " + str(len(history)) + " long: " + str(len(long_term)))
            
            full_response = ""
            try:
                if services.llm:
                    full_response = await chat_with_tools(user_message, history, system_prompt, client_id)
=======

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
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
                else:
                    full_response = "LLM not ready"
                    await manager.send(client_id, {"type": "chunk", "content": full_response})
            except Exception as ex:
                logger.error("Chat error: " + str(ex))
                full_response = "Error: " + str(ex)[:100]
                await manager.send(client_id, {"type": "error", "error": str(ex)})
            
            await manager.send(client_id, {"type": "done", "full_response": full_response})
<<<<<<< HEAD
            
=======

            # 保存到记忆
>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
            try:
                await save_short_term_message(user_id, "user", user_message)
                await save_short_term_message(user_id, "assistant", full_response)
                await save_long_term_memory(user_id, user_message, full_response)
<<<<<<< HEAD
            except Exception as ex:
                logger.error("Save memory failed: " + str(ex))
                
=======
            except Exception as e:
                logger.error(f"保存记忆失败: {e}")

>>>>>>> 17170295eece99f8f7c4c898415e4ea2afddad0e
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as ex:
        logger.error("WebSocket error: " + str(ex))
        manager.disconnect(client_id)
