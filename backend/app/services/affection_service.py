"""
好感度系统服务
- 管理用户与 Hiyori 的关系
- 等级 / 经验值 / 连续天数
"""
import os
import asyncpg
from datetime import datetime, date, timedelta
from typing import Optional, Dict
from loguru import logger


# 好感度等级定义
LEVELS = [
    {"min": 0,    "max": 10,   "level": "初识",   "level_en": "stranger",   "icon": "🌱"},
    {"min": 11,   "max": 50,   "level": "熟悉",   "level_en": "familiar",   "icon": "💕"},
    {"min": 51,   "max": 150,  "level": "喜欢",   "level_en": "like",       "icon": "💗"},
    {"min": 151,  "max": 500,  "level": "心动",   "level_en": "love",       "icon": "💖"},
    {"min": 501,  "max": 9999, "level": "深爱",   "level_en": "deeplove",   "icon": "💞"},
]


# 升级提示语
LEVEL_UP_MESSAGES = {
    "familiar": "*偷偷看主人* 主人,我们好像变熟悉了呢~ (｡♥‿♥｡)",
    "like": "诶? *脸红* Hiyori 好像有点喜欢主人...啊嘛...才不告诉你呢~ (｡>﹏<｡)",
    "love": "主人主人~ *偷偷蹭蹭* Hiyori 心跳好快啊...(´｡• ᵕ •｡`)",
    "deeplove": "主人!!! Hiyori 最最最喜欢主人了!!! 永远不要离开 Hiyori 啦~ ❤❤❤",
}


# 关键词增减规则
AFFECTION_KEYWORDS = {
    # 加分关键词
    "可爱": 3, "好看": 3, "漂亮": 3, "美": 3, "萌": 3,
    "我喜欢你": 5, "喜欢你": 5, "爱你": 5, "我爱你": 8,
    "想你": 5, "想念你": 5,
    "生日快乐": 10,
    "晚安": 2, "早安": 2, "午安": 2,
    "辛苦了": 3, "谢谢": 2, "感谢": 2,
    "棒": 2, "厉害": 2, "聪明": 2,
    # 减分关键词
    "讨厌你": -10, "讨厌": -5, "笨": -3, "蠢": -3,
    "滚": -10, "闭嘴": -5, "烦": -3,
    "废物": -8, "没用": -5,
}


class AffectionService:
    def __init__(self, pool=None):
        self.pool = pool  # 复用 auth 的连接池

    async def init_db(self, pool):
        """初始化好感度表"""
        self.pool = pool
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_relationships (
                        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                        affection INTEGER DEFAULT 0,
                        total_messages INTEGER DEFAULT 0,
                        days_active INTEGER DEFAULT 0,
                        streak_days INTEGER DEFAULT 0,
                        last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active_date DATE DEFAULT CURRENT_DATE,
                        current_level VARCHAR(20) DEFAULT 'stranger',
                        level_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            logger.info("OK Affection DB ready")
            return True
        except Exception as ex:
            logger.error("Affection DB init failed: " + str(ex))
            return False

    @staticmethod
    def get_level(affection: int) -> dict:
        """根据好感度返回等级信息"""
        for level in LEVELS:
            if level["min"] <= affection <= level["max"]:
                return level
        return LEVELS[-1]

    @staticmethod
    def calc_affection_change(message: str) -> int:
        """根据消息内容计算好感度变化"""
        change = 1  # 每条消息基础 +1
        msg_lower = message.lower()
        for keyword, score in AFFECTION_KEYWORDS.items():
            if keyword in message:
                change += score
        # 长消息额外奖励
        if len(message) > 50:
            change += 2
        # 限制单次变化范围
        return max(min(change, 15), -15)

    async def get_relationship(self, user_id: int) -> dict:
        """获取用户与 Hiyori 的关系"""
        if not self.pool:
            return self._default_relationship()
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT affection, total_messages, days_active, streak_days,
                              last_interaction, last_active_date, current_level
                       FROM user_relationships WHERE user_id = $1""",
                    user_id
                )
                if not row:
                    # 创建新记录
                    await conn.execute(
                        """INSERT INTO user_relationships (user_id) VALUES ($1)
                           ON CONFLICT DO NOTHING""",
                        user_id
                    )
                    return self._default_relationship()

                level = self.get_level(row["affection"])
                return {
                    "affection": row["affection"],
                    "total_messages": row["total_messages"],
                    "days_active": row["days_active"],
                    "streak_days": row["streak_days"],
                    "last_interaction": row["last_interaction"].isoformat() if row["last_interaction"] else None,
                    "level": level["level"],
                    "level_en": level["level_en"],
                    "level_icon": level["icon"],
                    "next_level_at": self._next_level_threshold(row["affection"])
                }
        except Exception as ex:
            logger.error("Get relationship failed: " + str(ex))
            return self._default_relationship()

    async def update_after_message(self, user_id: int, message: str) -> dict:
        """用户发消息后更新好感度,返回变化信息"""
        if not self.pool:
            return {"affection_change": 0, "level_up": None}

        try:
            change = self.calc_affection_change(message)

            async with self.pool.acquire() as conn:
                # 确保记录存在
                await conn.execute(
                    """INSERT INTO user_relationships (user_id) VALUES ($1)
                       ON CONFLICT DO NOTHING""",
                    user_id
                )

                # 获取当前状态
                row = await conn.fetchrow(
                    """SELECT affection, current_level, last_active_date, streak_days, days_active
                       FROM user_relationships WHERE user_id = $1""",
                    user_id
                )

                old_affection = row["affection"]
                old_level = row["current_level"]
                last_date = row["last_active_date"]
                streak = row["streak_days"]
                days_active = row["days_active"]

                # 计算新状态
                new_affection = max(0, old_affection + change)
                new_level_info = self.get_level(new_affection)
                new_level = new_level_info["level_en"]

                today = date.today()
                if last_date != today:
                    days_active += 1
                    if last_date and (today - last_date).days == 1:
                        streak += 1
                        # 连续 7 天奖励
                        if streak % 7 == 0:
                            new_affection += 5
                            change += 5
                    else:
                        streak = 1

                # 检查等级变化
                level_up = None
                if new_level != old_level:
                    level_up_index = next((i for i, l in enumerate(LEVELS) if l["level_en"] == new_level), -1)
                    old_level_index = next((i for i, l in enumerate(LEVELS) if l["level_en"] == old_level), -1)
                    if level_up_index > old_level_index:
                        level_up = {
                            "from": old_level,
                            "to": new_level,
                            "message": LEVEL_UP_MESSAGES.get(new_level, "诶?好像有点不一样了呢...")
                        }

                # 更新数据库
                await conn.execute(
                    """UPDATE user_relationships
                       SET affection = $1,
                           total_messages = total_messages + 1,
                           last_interaction = CURRENT_TIMESTAMP,
                           last_active_date = $2,
                           streak_days = $3,
                           days_active = $4,
                           current_level = $5,
                           level_changed_at = CASE
                               WHEN current_level != $5 THEN CURRENT_TIMESTAMP
                               ELSE level_changed_at
                           END
                       WHERE user_id = $6""",
                    new_affection, today, streak, days_active, new_level, user_id
                )

                return {
                    "affection": new_affection,
                    "affection_change": change,
                    "level": new_level_info["level"],
                    "level_en": new_level,
                    "level_icon": new_level_info["icon"],
                    "streak_days": streak,
                    "level_up": level_up
                }

        except Exception as ex:
            logger.error("Update relationship failed: " + str(ex))
            return {"affection_change": 0, "level_up": None}

    async def check_decay(self, user_id: int) -> int:
        """检查好感度衰减 (超过 3 天没来扣分)"""
        if not self.pool:
            return 0
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT affection, last_active_date FROM user_relationships
                       WHERE user_id = $1""",
                    user_id
                )
                if not row or not row["last_active_date"]:
                    return 0

                days_away = (date.today() - row["last_active_date"]).days
                if days_away >= 3:
                    decay = min(days_away - 2, 10)  # 最多扣 10
                    new_affection = max(0, row["affection"] - decay)
                    await conn.execute(
                        "UPDATE user_relationships SET affection = $1 WHERE user_id = $2",
                        new_affection, user_id
                    )
                    return -decay
                return 0
        except Exception as ex:
            logger.error("Check decay failed: " + str(ex))
            return 0

    def _default_relationship(self) -> dict:
        return {
            "affection": 0,
            "total_messages": 0,
            "days_active": 0,
            "streak_days": 0,
            "last_interaction": None,
            "level": "初识",
            "level_en": "stranger",
            "level_icon": "🌱",
            "next_level_at": 11
        }

    def _next_level_threshold(self, affection: int) -> int:
        """下一级需要多少好感度"""
        for level in LEVELS:
            if affection < level["min"]:
                return level["min"]
        return -1  # 已满级

    def get_personality_modifier(self, level_en: str) -> str:
        """根据等级返回额外的人格修饰提示"""
        modifiers = {
            "stranger": "你刚认识这位用户,语气稍微客气一些,但保持可爱。",
            "familiar": "你和这位用户已经熟悉了,语气更亲近,多撒娇。",
            "like": "你有点喜欢这位用户,经常主动找话题,会黏人。",
            "love": "你对这位用户心动了,常常害羞,关心备至,会用更多颜文字。",
            "deeplove": "你深爱这位用户,把ta当家人,撒娇打滚也不在乎。每句话都带满满的爱意。"
        }
        return modifiers.get(level_en, modifiers["stranger"])


# 全局实例
_affection_service = None


def get_affection_service():
    global _affection_service
    if _affection_service is None:
        _affection_service = AffectionService()
    return _affection_service
