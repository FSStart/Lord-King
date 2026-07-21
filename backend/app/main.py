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
import random
from datetime import datetime

from app.config import settings
from app.services.milvus_service import get_milvus_service
from app.services.llm_service import get_llm_service
from app.services.tools_service import TOOL_DEFINITIONS, execute_tool
from app.services.auth_service import get_auth_service, UserRegister, UserLogin
from app.services.affection_service import get_affection_service
from app.services.reminder_service import get_reminder_service
from app.services.companion_service import generate_proactive_message, get_idle_chatter
from app.services.profile_service import get_profile_service


class Services:
    milvus = None
    llm = None
    redis = None
    auth = None
    affection = None
    reminder = None
    profile = None
    skills = None
    mcp = None
    evolution = None


# === v6: Skills Engine + MCP + Self-Evolution ===
from app.services.skills import get_skills_engine
from app.services.mcp import MCPServer, setup_mcp_routes
from app.services.self_evolution import get_evolution_engine

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
            logger.info("OK Affection system ready")
        else:
            logger.warning("Affection: no auth pool, affection will return defaults!")
    except Exception as ex:
        logger.error("Affection init failed: " + str(ex))

    # 初始化日程提醒系统
    try:
        services.reminder = get_reminder_service()
        if services.auth and services.auth.pool:
            await services.reminder.init_db(services.auth.pool)
    except Exception as ex:
        logger.error("Reminder init failed: " + str(ex))

    # 初始化用户画像系统(功能4: 结构化记忆)
    try:
        services.profile = get_profile_service()
        if services.auth and services.auth.pool:
            await services.profile.init_db(services.auth.pool)
            logger.info("OK Profile system ready")
    except Exception as ex:
        logger.error("Profile init failed: " + str(ex))

    # === v6: Skills Engine ===
    try:
        services.skills = get_skills_engine()
        logger.info(f"OK Skills Engine ready: {len(services.skills.skills)} skills")
    except Exception as ex:
        logger.error(f"Skills Engine init failed: {ex}")

    # === v6: MCP Server ===
    try:
        from app.services.tools_service import TOOL_REGISTRY
        services.mcp = MCPServer(skills_engine=services.skills, tool_registry=TOOL_REGISTRY)
        setup_mcp_routes(app, services.mcp)
        logger.info("OK MCP Server ready")
    except Exception as ex:
        logger.error(f"MCP init failed: {ex}")

    # === v6: Self-Evolution Engine ===
    try:
        services.evolution = get_evolution_engine(llm_service=services.llm, skills_engine=services.skills)
        logger.info("OK Self-Evolution Engine ready")
    except Exception as ex:
        logger.error(f"Evolution init failed: {ex}")

    logger.info("OK Lord King startup complete! [v6]")
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


def _now_beijing():
    """获取北京时间(带 tzdata 缺失的兜底)"""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        # tzdata 缺失或 ZoneInfo 不可用时,手动 +8 小时
        from datetime import timezone, timedelta
        return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))


def build_system_prompt(user_id, long_term_memories, nickname="主人", relationship=None, proactive_recall=False, profile=None):
    # 当前北京时间(给 AI 用,避免它瞎猜或拿到 UTC 时间)
    now_bj = _now_beijing()
    weekday_zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now_bj.weekday()]
    time_str = now_bj.strftime("%Y年%m月%d日 ") + weekday_zh + now_bj.strftime(" %H:%M") + " (北京时间)"

    # 基础人格
    base = """You are Hiyori, a cute anime girl living in master's computer.

CURRENT TIME: """ + time_str + """ — 用户问时间/日期/星期时,直接基于此回答,不要调工具,不要瞎编时区.

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
You have access to tools. When user asks about weather, math, or needs to search for current info, use the tools. (For time/date, just use the CURRENT TIME above — no tool needed.) After getting results, respond in your cute Hiyori voice.

EMOTION TAG (重要,每次回复必须遵守):
回复的第一个字符必须是情绪标签,格式 [emotion:xxx],紧接着是正文,中间不要换行.
可选值(根据当前回复的氛围选最贴切的一个):
  happy     - 开心、兴奋、得意
  shy       - 害羞、被夸奖、脸红
  sad       - 难过、被冷落、委屈
  angry     - 生气、不满、撒娇式生气
  surprised - 惊讶、吃惊、意外
  love      - 喜欢、心动、撒娇示好
  neutral   - 正常、平静、日常对话
示例:
  [emotion:happy] 真的吗?好开心呀~ (≧≦)
  [emotion:shy] 啊...嘛...主人不要这样说啦~
  [emotion:neutral] 现在是下午三点哦.

RULES:
- ALWAYS reply in Chinese
- Keep responses cute and concise
- NEVER call yourself Nexus AI - you are Hiyori
- When using tool results, paraphrase in your cute style, don't just dump raw data
- 每次回复必须以 [emotion:xxx] 开头(见上面 EMOTION TAG 规则),不要忘记"""

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

    # 功能4: 结构化画像 —— 让 Hiyori 了解主人这个人(每轮注入)
    if profile:
        try:
            profile_text = get_profile_service().format_for_prompt(profile)
            if profile_text:
                base += profile_text
        except Exception:
            pass

    if long_term_memories:
        memory_lines = []
        for m in long_term_memories:
            memory_lines.append("- " + m)
        memory_text = "\n".join(memory_lines)
        base += "\n\nPrevious related conversations:\n" + memory_text

        # 功能4: 记忆主动提及 —— 偶尔让 Hiyori 主动想起过去的事,体现"记得 + 关心"
        if proactive_recall:
            base += ("\n\nPROACTIVE RECALL(本轮特别要求): 在自然回答用户的同时,主动、温柔地提起上面某一条"
                     "「以前聊过的事」,表现出你一直记得并关心主人(例如关心后续进展). 只提一条,自然融入,"
                     "不要生硬罗列,也不要说'根据我的记忆'这种话.")
    return base



# === v6: Skills & Evolution API ===

@app.get("/skills")
async def list_skills(current_user=Depends(get_current_user)):
    if not services.skills:
        return {"skills": [], "error": "Skills engine not ready"}
    return services.skills.get_status()

@app.get("/evolution")
async def evolution_report(current_user=Depends(get_current_user)):
    if not services.evolution:
        return {"error": "Evolution engine not ready"}
    return services.evolution.get_evolution_report()

@app.post("/evolution/generate-tool")
async def api_generate_tool(req: dict, current_user=Depends(get_current_user)):
    if not services.evolution:
        raise HTTPException(503, "Evolution engine not ready")
    result = await services.evolution.generate_tool(description=req.get("description", ""), tool_name=req.get("name"))
    return result

@app.post("/evolution/reflect")
async def api_reflect(current_user=Depends(get_current_user)):
    if not services.evolution:
        raise HTTPException(503, "Evolution engine not ready")
    return await services.evolution.reflect_and_improve()

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
    pitch: str = "+0Hz"  # 情绪驱动的音调,如 "+20Hz"(开心)/ "-15Hz"(难过)


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


@app.get("/profile")
async def get_profile(current_user=Depends(get_current_user)):
    """获取 Hiyori 记住的关于我的画像(功能4)"""
    if not services.profile:
        return {"profile": {}}
    user_id = int(current_user["user_id"])
    profile = await services.profile.get_profile(user_id)
    return {"profile": profile}


# ============ 日程提醒 API ============

class ReminderCreate(BaseModel):
    content: str
    remind_at: str  # ISO 格式 "2026-05-26T09:00:00"


class ReminderFromText(BaseModel):
    text: str  # 自然语言, 如 "明天9点提醒我开会"


@app.get("/reminders")
async def list_reminders(current_user=Depends(get_current_user)):
    """获取所有提醒"""
    if not services.reminder:
        raise HTTPException(status_code=503, detail="服务未就绪")
    user_id = int(current_user["user_id"])
    reminders = await services.reminder.list_reminders(user_id)
    return {"reminders": reminders, "count": len(reminders)}


@app.post("/reminders")
async def create_reminder(req: ReminderCreate, current_user=Depends(get_current_user)):
    """直接创建提醒"""
    if not services.reminder:
        raise HTTPException(status_code=503, detail="服务未就绪")
    user_id = int(current_user["user_id"])
    try:
        remind_at = datetime.fromisoformat(req.remind_at.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="时间格式错误,请用 ISO 格式")
    rid = await services.reminder.create_reminder(user_id, req.content, remind_at)
    if not rid:
        raise HTTPException(status_code=500, detail="创建失败")
    return {"id": rid, "content": req.content, "remind_at": req.remind_at}


@app.post("/reminders/parse")
async def parse_reminder(req: ReminderFromText, current_user=Depends(get_current_user)):
    """从自然语言文本创建提醒(智能解析)"""
    if not services.reminder:
        raise HTTPException(status_code=503, detail="服务未就绪")
    user_id = int(current_user["user_id"])
    remind_at = services.reminder.parse_time(req.text)
    if not remind_at:
        raise HTTPException(status_code=400, detail="无法解析时间,请说得清楚一些,比如'明天9点'")
    content = services.reminder.extract_content(req.text)
    rid = await services.reminder.create_reminder(user_id, content, remind_at)
    if not rid:
        raise HTTPException(status_code=500, detail="创建失败")
    return {
        "id": rid,
        "content": content,
        "remind_at": remind_at.isoformat(),
        "remind_at_human": remind_at.strftime("%Y-%m-%d %H:%M")
    }


@app.get("/reminders/pending")
async def get_pending_reminders(current_user=Depends(get_current_user)):
    """获取所有到期未提醒的(前端轮询此接口)"""
    if not services.reminder:
        return {"reminders": []}
    user_id = int(current_user["user_id"])
    pending = await services.reminder.get_pending_for_user(user_id)
    return {"reminders": pending, "count": len(pending)}


@app.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: int, current_user=Depends(get_current_user)):
    """删除提醒"""
    if not services.reminder:
        raise HTTPException(status_code=503, detail="服务未就绪")
    user_id = int(current_user["user_id"])
    ok = await services.reminder.delete_reminder(user_id, reminder_id)
    if not ok:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return {"status": "deleted"}


@app.post("/reminders/{reminder_id}/done")
async def mark_reminder_done(reminder_id: int, current_user=Depends(get_current_user)):
    """标记完成"""
    if not services.reminder:
        raise HTTPException(status_code=503, detail="服务未就绪")
    user_id = int(current_user["user_id"])
    ok = await services.reminder.mark_done(user_id, reminder_id)
    return {"status": "ok" if ok else "failed"}


# ============ 主动陪伴 API ============

@app.get("/proactive-greeting")
async def get_proactive_greeting(current_user=Depends(get_current_user)):
    """
    获取一条主动问候(用户打开网页时调用)
    根据当前时间、好感度、上次活跃时间生成
    """
    user_id = int(current_user["user_id"])
    nickname = current_user.get("username", "主人")

    # 获取用户信息
    if services.auth:
        user_info = await services.auth.get_user(user_id)
        if user_info and user_info.get("nickname"):
            nickname = user_info["nickname"]

    # 获取关系数据
    affection_level = "stranger"
    last_interaction = None
    last_active_date = None
    if services.affection:
        rel = await services.affection.get_relationship(user_id)
        affection_level = rel.get("level_en", "stranger")
        if rel.get("last_interaction"):
            try:
                last_interaction = datetime.fromisoformat(rel["last_interaction"])
            except Exception:
                pass
        # last_active_date 在 DB 里, 也查一下
        if services.auth and services.auth.pool:
            try:
                async with services.auth.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT last_active_date FROM user_relationships WHERE user_id = $1",
                        user_id
                    )
                    if row and row["last_active_date"]:
                        last_active_date = row["last_active_date"]
            except Exception:
                pass

    msg = await generate_proactive_message(
        user_id=user_id,
        nickname=nickname,
        affection_level=affection_level,
        last_interaction=last_interaction,
        last_active_date=last_active_date
    )
    if msg:
        return {"has_greeting": True, **msg}
    return {"has_greeting": False}


@app.get("/idle-chatter")
async def idle_chatter(current_user=Depends(get_current_user)):
    """
    空闲主动搭话(功能2: 桌宠化)
    前端在用户在线但静默一段时间后调用. 本地生成,零延迟零成本.
    有一定概率会主动提起一条过去的对话(功能4: 记忆主动提及).
    返回的 message 开头自带 [emotion:xxx],前端可直接驱动表情/语音.
    """
    user_id = int(current_user["user_id"])

    # 好感度等级
    level_en = "stranger"
    if services.affection:
        try:
            rel = await services.affection.get_relationship(user_id)
            level_en = rel.get("level_en", "stranger")
        except Exception:
            pass

    # 随机取一条历史记忆作为可能的"主动提起"素材(功能4)
    # 记忆格式为 "User: xxx | AI: yyy",这里只提取用户说过的话
    memory = None
    try:
        mems = await get_long_term_memories(user_id, "主人 最近 聊过 的事")
        if mems:
            raw = random.choice(mems)
            user_part = raw
            if raw.startswith("User:"):
                user_part = raw[len("User:"):]
            if "| AI:" in user_part:
                user_part = user_part.split("| AI:")[0]
            user_part = user_part.strip()
            if len(user_part) >= 4:
                memory = user_part
    except Exception:
        pass

    message = get_idle_chatter(level_en=level_en, memory=memory)
    return {"message": message, "level_en": level_en}


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


# ============ HTTP Chat (WebSocket 不可用时的兜底) ============

class ChatRequest(BaseModel):
    message: str
    images: Optional[List[str]] = None  # base64 data URL 列表(功能1: 视觉)

@app.post("/chat")
async def http_chat(req: ChatRequest, current_user=Depends(get_current_user)):
    user_id = str(current_user["user_id"])
    username = current_user["username"]
    nickname = username
    try:
        user_info = await services.auth.get_user(int(user_id))
        if user_info and user_info.get("nickname"):
            nickname = user_info["nickname"]
    except:
        pass

    relationship = None
    if services.affection:
        try:
            await services.affection.check_decay(int(user_id))
            relationship = await services.affection.get_relationship(int(user_id))
        except Exception as ex:
            logger.error("Get relationship failed: " + str(ex))
    mcp = None
    evolution = None
    if services.profile:
        try:
            profile = await services.profile.get_profile(int(user_id))
        except Exception:
            pass

    history = await get_short_term_history(user_id)
    long_term = await get_long_term_memories(user_id, req.message)
    system_prompt = build_system_prompt(user_id, long_term, nickname=nickname,
                                        relationship=relationship, profile=profile)

    client_id = "http_" + user_id
    try:
        response = await chat_with_tools(req.message, history, system_prompt, client_id,
                                         user_id=user_id, images=req.images or [])
    except Exception as ex:
        logger.error("HTTP chat error: " + str(ex))
        raise HTTPException(status_code=500, detail=str(ex))

    if services.affection:
        try:
            await services.affection.update_after_message(int(user_id), req.message)
        except:
            pass

    await save_short_term_message(user_id, "user", req.message)
    await save_short_term_message(user_id, "assistant", response)
    if services.milvus:
        try:
            await services.milvus.add_memory(user_id, req.message + "\n" + response)
        except:
            pass

    # 功能4: 后台更新结构化画像
    if services.profile and services.llm and req.message:
        asyncio.create_task(
            services.profile.update_from_exchange(int(user_id), req.message, services.llm)
        )

    return {"response": response}


# ============ TTS ============

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    import edge_tts
    last_ex = None
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(
                text=request.text, voice=request.voice,
                rate=request.rate, volume=request.volume, pitch=request.pitch
            )
            audio_data = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])
            audio_data.seek(0)
            content = audio_data.read()
            if content:
                return Response(content=content, media_type="audio/mpeg",
                               headers={"Cache-Control": "no-cache"})
            last_ex = Exception("No audio received")
        except Exception as ex:
            last_ex = ex
            logger.warning(f"TTS attempt {attempt + 1} failed: {ex}")
            if attempt < 2:
                await asyncio.sleep(0.5)
    logger.error(f"TTS failed after 3 attempts: {last_ex}")
    raise HTTPException(status_code=500, detail="TTS failed: " + str(last_ex))


# ============ 工具调用 ============

async def chat_with_tools(user_message, history, system_prompt, client_id, user_id=None, images=None):
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)

    # 功能1: 多模态视觉 —— 用户发了图片时,组多模态 content 并切到 VL 模型(跳过工具,直接流式)
    if images:
        client = services.llm.client
        vl_model = getattr(settings, "QWEN_VL_MODEL", None) or services.llm.model
        user_content = [{"type": "text", "text": user_message or "看看这张图片~"}]
        for img in images:
            if img:
                user_content.append({"type": "image_url", "image_url": {"url": img}})
        messages.append({"role": "user", "content": user_content})
        await manager.send(client_id, {"type": "status", "status": "looking"})
        try:
            stream = await client.chat.completions.create(
                model=vl_model, messages=messages, stream=True
            )
            full_response = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    await manager.send(client_id, {"type": "chunk", "content": content})
            return full_response
        except Exception as e:
            logger.error("Vision chat failed: " + str(e))
            await manager.send(client_id, {"type": "chunk", "content": "[emotion:sad] 呜...Hiyori 看不清这张图片呐 (｡>﹏<｡)"})
            return "[emotion:sad] 呜...Hiyori 看不清这张图片呐"

    messages.append({"role": "user", "content": user_message})

    try:
        client = services.llm.client
        model = services.llm.model

        # AsyncOpenAI 的 create() 返回 coroutine,必须直接 await,
        # 不能用 asyncio.to_thread(会把 coroutine 当结果返回)
        response = await client.chat.completions.create(
            model=model, messages=messages,
            tools=TOOL_DEFINITIONS + (services.skills.get_tool_definitions() if services.skills else []), tool_choice="auto", stream=False
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
                # v6: try skills engine first if not in TOOL_REGISTRY
                from app.services.tools_service import TOOL_REGISTRY as _base_registry
                if tool_name not in _base_registry and services.skills and tool_name in services.skills.tool_funcs:
                    tool_result = await services.skills.execute_tool(tool_name, tool_args, user_id=int(user_id) if user_id else None)
                else:
                    tool_result = await execute_tool(tool_name, tool_args, user_id=int(user_id) if user_id else None)
                messages.append({
                    "role": "tool", "tool_call_id": tc.id, "content": tool_result
                })

            stream = await client.chat.completions.create(
                model=model, messages=messages, stream=True
            )

            full_response = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    await manager.send(client_id, {"type": "chunk", "content": content})
            return full_response

        else:
            stream = await client.chat.completions.create(
                model=model, messages=messages, stream=True
            )
            full_response = ""
            async for chunk in stream:
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
            images = message_data.get("images") or []
            # 既没文字也没图片才跳过
            if not user_message and not images:
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
            # 取结构化画像(功能4)
            profile = None
            if services.profile:
                try:
                    profile = await services.profile.get_profile(int(user_id))
                except Exception:
                    pass
            # 有长期记忆时,~18% 概率让 Hiyori 主动提起过去的事
            proactive_recall = bool(long_term) and random.random() < 0.18
            system_prompt = build_system_prompt(user_id, long_term, nickname=nickname,
                                                relationship=relationship, proactive_recall=proactive_recall,
                                                profile=profile)

            logger.info("[" + username + "] short: " + str(len(history)) + " long: " + str(len(long_term)) +
                       " img: " + str(len(images)) +
                       " affection: " + str(relationship.get("affection", 0) if relationship else 0))

            full_response = ""
            try:
                if services.llm:
                    full_response = await chat_with_tools(user_message, history, system_prompt, client_id, user_id=user_id, images=images)
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

            # 功能4: 后台抽取/更新结构化画像(不阻塞,失败无所谓)
            if services.profile and services.llm and user_message:
                asyncio.create_task(
                    services.profile.update_from_exchange(int(user_id), user_message, services.llm)
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as ex:
        logger.error("WebSocket error: " + str(ex))
        manager.disconnect(client_id)
