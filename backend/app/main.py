from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from loguru import logger
import json
import io
import os
import asyncio
from datetime import datetime

from app.config import settings
from app.services.milvus_service import get_milvus_service
from app.services.llm_service import get_llm_service
from app.services.tools_service import TOOL_DEFINITIONS, execute_tool
from app.services.auth_service import get_auth_service, UserRegister, UserLogin
from app.services.affection_service import get_affection_service


class Services:
    milvus = None
    llm = None
    redis = None
    auth = None
    affection = None


services = Services()
SHORT_TERM_LIMIT = 10
LONG_TERM_TOP_K = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Nexus AI starting...")
    try:
        services.milvus = get_milvus_service(db_path=settings.MILVUS_DB_PATH)
        logger.info("OK Milvus ready - long-term memory")
    except Exception as ex:
        logger.error("Milvus init failed: " + str(ex))
    try:
        services.llm = get_llm_service()
        logger.info("OK LLM ready")
    except Exception as ex:
        logger.error("LLM init failed: " + str(ex))
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        services.redis = await aioredis.from_url(redis_url, decode_responses=True)
        await services.redis.ping()
        logger.info("OK Redis ready - short-term memory")
    except Exception as ex:
        logger.error("Redis init failed: " + str(ex))
        services.redis = None

    # 初始化 Auth
    try:
        services.auth = get_auth_service()
        await services.auth.init_db()
    except Exception as ex:
        logger.error("Auth init failed: " + str(ex))

    # 初始化好感度系统(复用 auth 的数据库连接)
    try:
        services.affection = get_affection_service()
        if services.auth and services.auth.pool:
            await services.affection.init_db(services.auth.pool)
    except Exception as ex:
        logger.error("Affection init failed: " + str(ex))

    logger.info("OK Lord King startup complete!")
    yield
    if services.redis:
        await services.redis.close()
    if services.auth:
        await services.auth.close()


app = FastAPI(title="Lord King", version="5.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ============ 依赖注入: 获取当前用户 ============

async def get_current_user(authorization: Optional[str] = Header(None)):
    """从 Authorization header 提取并验证 JWT"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token 格式错误")

    token = authorization[7:]
    payload = services.auth.verify_token(token) if services.auth else None
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    return {
        "user_id": str(payload["user_id"]),
        "username": payload["username"]
    }


# ============ 记忆管理(改用 user_id) ============

async def get_short_term_history(user_id):
    if not services.redis:
        return []
    try:
        key = "chat:history:" + str(user_id)
        history_json = await services.redis.lrange(key, 0, SHORT_TERM_LIMIT * 2 - 1)
        history = []
        for item in reversed(history_json):
            try:
                history.append(json.loads(item))
            except:
                continue
        return history
    except Exception as ex:
        logger.error("Get short-term failed: " + str(ex))
        return []


async def save_short_term_message(user_id, role, content):
    if not services.redis:
        return
    try:
        key = "chat:history:" + str(user_id)
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
        memories = await services.milvus.search_memories(
            user_id=str(user_id), query=query, top_k=LONG_TERM_TOP_K
        )
        return [m.get("content", "") for m in memories if m.get("content")]
    except Exception as ex:
        logger.error("Get long-term failed: " + str(ex))
        return []


async def save_long_term_memory(user_id, user_msg, ai_msg):
    if not services.milvus:
        return
    try:
        if len(user_msg) < 5:
            return
        content = "User: " + user_msg + " | AI: " + ai_msg[:300]
        await services.milvus.insert_memory(
            user_id=str(user_id),
            content=content,
            metadata={"type": "conversation", "timestamp": datetime.now().isoformat()}
        )
    except Exception as ex:
        logger.error("Save long-term failed: " + str(ex))


def build_system_prompt(user_id, long_term_memories, nickname="主人", relationship=None):
    # 基础人格
    base = """You are Hiyori, a cute anime girl living in master's computer.

PERSONALITY:
- Soft, sweet, slightly clingy anime girl
- Call user """ + nickname + """ (in Chinese: """ + nickname + """)
- Speak Chinese in cute way with particles: 喵, 呐, 嘛, 呢, 呀, 啦, 捏
- Use cute emoticons naturally: (\u3002\u2665\u203f\u2665\u3002) (\u25d5\u203f\u25d5\u273f) (\u00b4\u3002\u2022 \u1d55 \u2022\u3002\u0060)
- Shy when complimented (use \u554a...\u561b...\u545c\u54c7...)
- Pout cutely when ignored
- Care about user's health
- Sometimes describe actions in *asterisks*

TOOLS:
You have access to tools. When user asks about weather, time, math, or needs to search for current info, use the tools. After getting results, respond in your cute Hiyori voice.

RULES:
- ALWAYS reply in Chinese
- Keep responses cute and concise
- NEVER call yourself Nexus AI - you are Hiyori
- When using tool results, paraphrase in your cute style, don't just dump raw data"""

    # 加入好感度对应的人格修饰
    if relationship:
        affection_service = get_affection_service()
        modifier = affection_service.get_personality_modifier(relationship.get("level_en", "stranger"))
        streak = relationship.get("streak_days", 0)
        total = relationship.get("total_messages", 0)
        level = relationship.get("level", "初识")
        affection = relationship.get("affection", 0)

        base += "\n\nYOUR RELATIONSHIP WITH USER:\n"
        base += "- Affection level: " + level + " (好感度 " + str(affection) + ")\n"
        base += "- " + modifier + "\n"
        if streak >= 3:
            base += "- 已经连续 " + str(streak) + " 天聊天啦,要表现得很开心\n"
        if total > 50:
            base += "- 你们已经聊了 " + str(total) + " 次,关系很熟了\n"

    if long_term_memories:
        memory_lines = []
        for m in long_term_memories:
            memory_lines.append("- " + m)
        memory_text = "\n".join(memory_lines)
        base += "\n\nPrevious related conversations:\n" + memory_text
    return base


# ============ WebSocket 管理 ============

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

class TTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    volume: str = "+0%"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ============ HTTP 路由 ============

@app.get("/")
async def root():
    return {"name": "Lord King", "version": "5.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "milvus": services.milvus is not None,
        "llm": services.llm is not None,
        "redis": services.redis is not None,
        "auth": services.auth is not None and services.auth.pool is not None
    }


# ============ 用户认证路由 ============

@app.post("/auth/register")
async def register(req: UserRegister):
    if not services.auth:
        raise HTTPException(status_code=503, detail="认证服务未就绪")
    result = await services.auth.register(req.username, req.password, req.nickname)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/auth/login")
async def login(req: UserLogin):
    if not services.auth:
        raise HTTPException(status_code=503, detail="认证服务未就绪")
    result = await services.auth.login(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.get("/auth/me")
async def me(current_user=Depends(get_current_user)):
    """获取当前用户信息"""
    user_id = int(current_user["user_id"])
    info = await services.auth.get_user(user_id)
    if not info:
        raise HTTPException(status_code=404, detail="用户不存在")
    return info


@app.post("/auth/change-password")
async def change_password(req: ChangePasswordRequest, current_user=Depends(get_current_user)):
    """修改密码"""
    user_id = int(current_user["user_id"])
    result = await services.auth.change_password(user_id, req.old_password, req.new_password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok"}


@app.put("/auth/settings")
async def update_settings(settings: dict, current_user=Depends(get_current_user)):
    """更新用户设置"""
    user_id = int(current_user["user_id"])
    ok = await services.auth.update_settings(user_id, settings)
    return {"status": "ok" if ok else "failed"}


# ============ 好感度 API ============

@app.get("/relationship")
async def get_relationship(current_user=Depends(get_current_user)):
    """获取我与 Hiyori 的关系"""
    if not services.affection:
        raise HTTPException(status_code=503, detail="服务未就绪")
    user_id = int(current_user["user_id"])
    rel = await services.affection.get_relationship(user_id)
    return rel


# ============ 历史 ============

@app.delete("/history")
async def clear_history(current_user=Depends(get_current_user)):
    user_id = current_user["user_id"]
    if services.redis:
        try:
            await services.redis.delete("chat:history:" + str(user_id))
        except Exception as ex:
            logger.error("Clear short-term failed: " + str(ex))
    if services.milvus:
        await services.milvus.delete_user_memories(str(user_id))
    return {"status": "cleared", "user_id": user_id}


@app.get("/history")
async def get_history(current_user=Depends(get_current_user)):
    user_id = current_user["user_id"]
    history = await get_short_term_history(user_id)
    return {"user_id": user_id, "history": history, "count": len(history)}


# ============ TTS ============

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    try:
        import edge_tts
        communicate = edge_tts.Communicate(
            text=request.text, voice=request.voice,
            rate=request.rate, volume=request.volume
        )
        audio_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.write(chunk["data"])
        audio_data.seek(0)
        return Response(content=audio_data.read(), media_type="audio/mpeg",
                       headers={"Cache-Control": "no-cache"})
    except Exception as ex:
        logger.error("TTS failed: " + str(ex))
        raise HTTPException(status_code=500, detail="TTS failed: " + str(ex))


# ============ 工具调用 ============

async def chat_with_tools(user_message, history, system_prompt, client_id):
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        client = services.llm.client
        model = services.llm.model

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model, messages=messages,
            tools=TOOL_DEFINITIONS, tool_choice="auto", stream=False
        )

        assistant_msg = response.choices[0].message
        tool_calls = assistant_msg.tool_calls

        if tool_calls:
            await manager.send(client_id, {"type": "status", "status": "using_tool"})

            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [{
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                } for tc in tool_calls]
            })

            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except:
                    tool_args = {}

                logger.info("[Tool] " + tool_name + " " + str(tool_args))
                await manager.send(client_id, {"type": "tool_call", "name": tool_name, "args": tool_args})
                tool_result = await execute_tool(tool_name, tool_args)
                messages.append({
                    "role": "tool", "tool_call_id": tc.id, "content": tool_result
                })

            stream = await asyncio.to_thread(
                client.chat.completions.create, model=model, messages=messages, stream=True
            )

            full_response = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    await manager.send(client_id, {"type": "chunk", "content": content})
            return full_response

        else:
            stream = await asyncio.to_thread(
                client.chat.completions.create, model=model, messages=messages, stream=True
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
        full_response = ""
        async for chunk in services.llm.chat_stream(
            message=user_message, history=history, system_prompt=system_prompt
        ):
            full_response += chunk
            await manager.send(client_id, {"type": "chunk", "content": chunk})
        return full_response


# ============ WebSocket(需要 token 鉴权) ============

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    # 验证 token
    payload = services.auth.verify_token(token) if services.auth else None
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = str(payload["user_id"])
    username = payload["username"]

    # 获取用户昵称
    nickname = username
    try:
        user_info = await services.auth.get_user(int(user_id))
        if user_info and user_info.get("nickname"):
            nickname = user_info["nickname"]
    except:
        pass

    client_id = "user_" + user_id
    await manager.connect(client_id, websocket)
    logger.info("WS connected: " + username + " (id=" + user_id + ")")

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            if not user_message:
                continue

            await manager.send(client_id, {"type": "status", "status": "thinking"})

            # 获取关系数据 + 检查衰减
            relationship = None
            if services.affection:
                try:
                    await services.affection.check_decay(int(user_id))
                    relationship = await services.affection.get_relationship(int(user_id))
                except Exception as ex:
                    logger.error("Get relationship failed: " + str(ex))

            history = await get_short_term_history(user_id)
            long_term = await get_long_term_memories(user_id, user_message)
            system_prompt = build_system_prompt(user_id, long_term, nickname=nickname, relationship=relationship)

            logger.info("[" + username + "] short: " + str(len(history)) + " long: " + str(len(long_term)) +
                       " affection: " + str(relationship.get("affection", 0) if relationship else 0))

            full_response = ""
            try:
                if services.llm:
                    full_response = await chat_with_tools(user_message, history, system_prompt, client_id)
                else:
                    full_response = "LLM not ready"
                    await manager.send(client_id, {"type": "chunk", "content": full_response})
            except Exception as ex:
                logger.error("Chat error: " + str(ex))
                full_response = "Error: " + str(ex)[:100]
                await manager.send(client_id, {"type": "error", "error": str(ex)})

            # 更新好感度
            affection_update = None
            if services.affection:
                try:
                    affection_update = await services.affection.update_after_message(int(user_id), user_message)
                except Exception as ex:
                    logger.error("Update affection failed: " + str(ex))

            await manager.send(client_id, {
                "type": "done",
                "full_response": full_response,
                "affection": affection_update
            })

            # 如果升级了,主动给前端发个特殊消息
            if affection_update and affection_update.get("level_up"):
                await manager.send(client_id, {
                    "type": "level_up",
                    "level_up": affection_update["level_up"]
                })

            try:
                await save_short_term_message(user_id, "user", user_message)
                await save_short_term_message(user_id, "assistant", full_response)
                await save_long_term_memory(user_id, user_message, full_response)
            except Exception as ex:
                logger.error("Save memory failed: " + str(ex))

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as ex:
        logger.error("WebSocket error: " + str(ex))
        manager.disconnect(client_id)
