"""
用户画像服务 (功能4: 结构化记忆)
- 从对话里抽取关于主人的事实(称呼/生日/职业/喜好/在意的事/重要的人...)
- 以结构化 JSON 存进 Postgres(复用 auth 连接池)
- 注入 system prompt, 让 Hiyori 真的"懂你", 而不是偶尔蹦一句旧对话

和 Milvus 长期记忆的区别:
- Milvus 存的是"对话片段", 靠语义检索召回, 是"她记得我们聊过什么"
- Profile 存的是"关于你的事实", 每轮都注入, 是"她了解你这个人"
两者互补.
"""
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict
from loguru import logger


# 画像的字段(给 LLM 抽取时参考, 也用于格式化)
PROFILE_FIELDS = {
    "nickname": "主人希望被怎么称呼",
    "birthday": "生日(MM-DD 或 YYYY-MM-DD)",
    "job": "职业 / 工作 / 在做的事",
    "location": "所在城市 / 地区",
    "likes": "喜好(喜欢的东西/食物/游戏/番剧/音乐等, 数组)",
    "dislikes": "讨厌/不喜欢的东西(数组)",
    "important_people": "重要的人(家人/朋友/宠物, 数组)",
    "current_things": "最近在忙/在意/在追的事(数组, 会随时间更新)",
    "goals": "目标 / 愿望 / 计划(数组)",
    "notes": "其它值得记住的零碎事实(数组)",
}

_LIST_FIELDS = {"likes", "dislikes", "important_people", "current_things", "goals", "notes"}

EXTRACT_SYSTEM = """你是一个信息抽取器. 从主人(user)最新的一句话里, 抽取关于他本人的、值得长期记住的【事实】, 合并进已有画像.

只抽取稳定的个人事实(称呼、生日、职业、所在地、长期喜好/厌恶、重要的人、最近在忙/在追的事、目标愿望、其它重要零碎).
不要抽取: 闲聊、对 AI 的称赞、一次性的提问、临时情绪、与主人本人无关的内容.

输出严格的 JSON 对象, 字段从这些里选(没有新信息的字段不要出现):
- nickname(字符串) birthday(字符串) job(字符串) location(字符串)
- likes/dislikes/important_people/current_things/goals/notes(字符串数组, 每项简短)

规则:
- 没有任何值得记的新事实时, 输出 {}
- 数组字段只输出【新增】的项, 不要重复已有画像里的内容
- 用中文, 每项尽量短(几个字到一句话)
- 只输出 JSON, 不要任何解释、不要 markdown 代码块"""


class ProfileService:
    def __init__(self, pool=None):
        self.pool = pool

    async def init_db(self, pool):
        self.pool = pool
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                        data JSONB DEFAULT '{}'::jsonb,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            logger.info("OK Profile DB ready")
            return True
        except Exception as ex:
            logger.error("Profile DB init failed: " + str(ex))
            return False

    async def get_profile(self, user_id: int) -> Dict:
        if not self.pool:
            return {}
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT data FROM user_profiles WHERE user_id = $1", user_id
                )
                if row and row["data"]:
                    data = row["data"]
                    if isinstance(data, str):
                        data = json.loads(data)
                    return data or {}
        except Exception as ex:
            logger.error("Get profile failed: " + str(ex))
        return {}

    async def _save_profile(self, user_id: int, data: Dict):
        if not self.pool:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO user_profiles (user_id, data, updated_at)
                       VALUES ($1, $2::jsonb, CURRENT_TIMESTAMP)
                       ON CONFLICT (user_id)
                       DO UPDATE SET data = $2::jsonb, updated_at = CURRENT_TIMESTAMP""",
                    user_id, json.dumps(data, ensure_ascii=False),
                )
        except Exception as ex:
            logger.error("Save profile failed: " + str(ex))

    @staticmethod
    def format_for_prompt(profile: Dict) -> str:
        """把画像格式化成注入 system prompt 的一段文字"""
        if not profile:
            return ""
        lines = []
        labels = {
            "nickname": "称呼", "birthday": "生日", "job": "职业",
            "location": "所在地", "likes": "喜欢", "dislikes": "讨厌",
            "important_people": "重要的人", "current_things": "最近在忙/在意",
            "goals": "目标愿望", "notes": "其它",
        }
        for key, label in labels.items():
            val = profile.get(key)
            if not val:
                continue
            if isinstance(val, list):
                val = "、".join(str(v) for v in val if v)
            if val:
                lines.append("- " + label + ": " + str(val))
        if not lines:
            return ""
        return ("\n\nWHAT YOU KNOW ABOUT MASTER(你了解的主人画像, 自然地体现你懂他, "
                "不要生硬罗列, 不要说'根据资料'):\n" + "\n".join(lines))

    def _merge(self, old: Dict, new: Dict) -> Dict:
        """把新抽取的事实合并进旧画像. 数组去重追加, 标量覆盖."""
        merged = dict(old or {})
        for key, val in (new or {}).items():
            if key not in PROFILE_FIELDS or val in (None, "", [], {}):
                continue
            if key in _LIST_FIELDS:
                cur = merged.get(key) or []
                if not isinstance(cur, list):
                    cur = [cur]
                incoming = val if isinstance(val, list) else [val]
                for item in incoming:
                    item = str(item).strip()
                    if item and item not in cur:
                        cur.append(item)
                # 控制每个列表长度上限, 防止无限膨胀(保留最近的)
                merged[key] = cur[-12:]
            else:
                merged[key] = str(val).strip()
        return merged

    async def update_from_exchange(self, user_id: int, user_msg: str, llm) -> Optional[Dict]:
        """
        从一轮对话里抽取事实并更新画像. 设计为后台 fire-and-forget 调用, 不阻塞回复.
        llm: LLMService 实例(复用其 client/model).
        """
        if not self.pool or not llm or not getattr(llm, "client", None):
            return None
        user_msg = (user_msg or "").strip()
        if len(user_msg) < 6:
            return None

        try:
            existing = await self.get_profile(user_id)
            existing_brief = json.dumps(existing, ensure_ascii=False)[:1500]
            prompt = ("已有画像:\n" + existing_brief +
                      "\n\n主人最新的话:\n" + user_msg[:800] +
                      "\n\n请输出要新增/更新的字段 JSON:")

            raw = await self._call_llm(llm, prompt)
            new_facts = self._parse_json(raw)
            if not new_facts:
                return None

            merged = self._merge(existing, new_facts)
            if merged != existing:
                await self._save_profile(user_id, merged)
                logger.info(f"[Profile] user={user_id} updated: {list(new_facts.keys())}")
            return merged
        except Exception as ex:
            logger.error("update_from_exchange failed: " + str(ex))
            return None

    async def _call_llm(self, llm, prompt: str) -> str:
        """用最省的方式调一次 LLM 做抽取(走 OpenAI 兼容 或 Anthropic)"""
        try:
            if getattr(llm, "use_qwen", False):
                resp = await llm.client.chat.completions.create(
                    model=llm.model,
                    messages=[
                        {"role": "system", "content": EXTRACT_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=400,
                    temperature=0,
                )
                return resp.choices[0].message.content or ""
            else:
                resp = await llm.client.messages.create(
                    model=llm.model,
                    max_tokens=400,
                    system=EXTRACT_SYSTEM,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp.content[0].text if resp.content else ""
        except Exception as ex:
            logger.warning("Profile LLM extract failed: " + str(ex))
            return ""

    @staticmethod
    def _parse_json(raw: str) -> Optional[Dict]:
        if not raw:
            return None
        raw = raw.strip()
        # 去掉可能的 ```json 包裹
        if raw.startswith("```"):
            raw = raw.split("```")[1] if "```" in raw[3:] else raw
            raw = raw.replace("json", "", 1).strip("` \n")
        # 截取第一个 { 到最后一个 }
        l, r = raw.find("{"), raw.rfind("}")
        if l == -1 or r == -1 or r < l:
            return None
        try:
            data = json.loads(raw[l:r + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            return None


_profile_service = None


def get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service
