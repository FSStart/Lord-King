"""
日程提醒服务
- 创建/查询/删除日程
- 智能解析自然语言时间
- 到点触发提醒
"""
import os
import re
import asyncpg
from datetime import datetime, timedelta, date, time
from typing import Optional, List
from loguru import logger


class ReminderService:
    def __init__(self, pool=None):
        self.pool = pool

    async def init_db(self, pool):
        """初始化日程表"""
        self.pool = pool
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        content TEXT NOT NULL,
                        remind_at TIMESTAMP NOT NULL,
                        repeat_type VARCHAR(20) DEFAULT 'once',
                        is_done BOOLEAN DEFAULT FALSE,
                        is_notified BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_reminders_user_time ON reminders(user_id, remind_at)"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_reminders_pending ON reminders(is_notified, remind_at) WHERE is_done = FALSE"
                )
            logger.info("OK Reminder DB ready")
            return True
        except Exception as ex:
            logger.error("Reminder DB init failed: " + str(ex))
            return False

    @staticmethod
    def parse_time(text: str, base_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        智能解析自然语言时间
        支持: "明天9点", "10分钟后", "下周三", "今晚8点" 等
        """
        if not base_time:
            base_time = datetime.now()
        text = text.strip()

        # === 相对时间 ===
        # "10分钟后"
        m = re.search(r"(\d+)\s*分钟[后内之]?", text)
        if m:
            return base_time + timedelta(minutes=int(m.group(1)))

        # "2小时后"
        m = re.search(r"(\d+)\s*[小时个钟]+[后内之]?", text)
        if m:
            return base_time + timedelta(hours=int(m.group(1)))

        # "1天后" 或 "明天" 后续会处理时间
        m = re.search(r"(\d+)\s*天[后内之]?", text)
        days_offset = 0
        if m:
            days_offset = int(m.group(1))

        # === 日期关键词 ===
        if "今天" in text or "今晚" in text:
            target_date = base_time.date()
        elif "明天" in text or "明晚" in text:
            target_date = base_time.date() + timedelta(days=1)
        elif "后天" in text:
            target_date = base_time.date() + timedelta(days=2)
        elif "大后天" in text:
            target_date = base_time.date() + timedelta(days=3)
        elif days_offset > 0:
            target_date = base_time.date() + timedelta(days=days_offset)
        else:
            # 默认今天
            target_date = base_time.date()

        # === 时间解析 ===
        # "上午8点" "下午3点" "晚上9点" "9:30" "9点30分" "9点半"
        target_hour = None
        target_minute = 0

        # 9:30 或 9点30分 或 9点半
        m = re.search(r"(\d{1,2})\s*[:：点]\s*(\d{1,2}|半)\s*分?", text)
        if m:
            target_hour = int(m.group(1))
            min_str = m.group(2)
            target_minute = 30 if min_str == "半" else int(min_str)
        else:
            # 仅 "9点"
            m = re.search(r"(\d{1,2})\s*[点时]", text)
            if m:
                target_hour = int(m.group(1))

        # 判断是上午还是下午
        if target_hour is not None:
            if "下午" in text or "傍晚" in text:
                if target_hour < 12:
                    target_hour += 12
            elif "晚上" in text or "晚" in text or "今晚" in text or "明晚" in text:
                if target_hour < 12:
                    target_hour += 12
                # "晚上 12 点" 通常指 0 点
                if target_hour == 24:
                    target_hour = 0
                    target_date += timedelta(days=1)
            elif "凌晨" in text:
                if target_hour >= 12:
                    target_hour -= 12

        # 如果没解析出时间,且只是说了"明天","后天"等,默认 9:00
        if target_hour is None:
            if any(kw in text for kw in ["明天", "后天", "今天"]) and "点" not in text:
                target_hour = 9
            else:
                return None

        # 合成最终时间
        try:
            target = datetime.combine(
                target_date,
                time(hour=target_hour % 24, minute=target_minute)
            )
            # 如果是今天但时间已过,移到明天
            if target < base_time and "今" not in text and days_offset == 0:
                # 不修正,因为可能用户就是想要"过去的某个时间"(虽然没意义)
                pass
            return target
        except (ValueError, TypeError):
            return None

    @staticmethod
    def extract_content(text: str) -> str:
        """
        从用户消息中提取提醒内容
        例如: "提醒我明天9点开会" -> "开会"
        """
        # 删除时间相关词
        patterns = [
            r"提醒我?",
            r"请提醒",
            r"明天上?午?下?午?晚?上?",
            r"今天上?午?下?午?晚?上?",
            r"后天",
            r"\d+\s*分钟[后内之]?",
            r"\d+\s*[小时个钟]+[后内之]?",
            r"\d+\s*天[后内之]?",
            r"\d{1,2}\s*[:：点时]\s*\d{0,2}\s*分?",
            r"\d{1,2}\s*[点时]半?",
            r"上?午?下?午?晚?上?凌晨?",
            r"\s+",
        ]
        content = text
        for p in patterns:
            content = re.sub(p, " ", content)
        content = re.sub(r"\s+", " ", content).strip()
        # 删除句首句尾的"我"和虚词
        content = re.sub(r"^[我去要请吧呢呐]+", "", content).strip()
        content = re.sub(r"[吧呢呐喵呀啦哦~]+$", "", content).strip()
        return content or "提醒"

    async def create_reminder(
        self, user_id: int, content: str, remind_at: datetime
    ) -> Optional[int]:
        """创建提醒"""
        if not self.pool:
            return None
        try:
            async with self.pool.acquire() as conn:
                rid = await conn.fetchval(
                    """INSERT INTO reminders (user_id, content, remind_at)
                       VALUES ($1, $2, $3) RETURNING id""",
                    user_id, content, remind_at
                )
                logger.info("Reminder created: id=" + str(rid) + " for user " + str(user_id) +
                          " at " + remind_at.isoformat())
                return rid
        except Exception as ex:
            logger.error("Create reminder failed: " + str(ex))
            return None

    async def list_reminders(self, user_id: int, include_done: bool = False) -> List[dict]:
        """查询用户的所有提醒"""
        if not self.pool:
            return []
        try:
            async with self.pool.acquire() as conn:
                query = """SELECT id, content, remind_at, is_done, is_notified, created_at
                           FROM reminders WHERE user_id = $1"""
                if not include_done:
                    query += " AND is_done = FALSE"
                query += " ORDER BY remind_at ASC LIMIT 100"
                rows = await conn.fetch(query, user_id)
                return [
                    {
                        "id": r["id"],
                        "content": r["content"],
                        "remind_at": r["remind_at"].isoformat(),
                        "is_done": r["is_done"],
                        "is_notified": r["is_notified"],
                        "created_at": r["created_at"].isoformat() if r["created_at"] else None
                    }
                    for r in rows
                ]
        except Exception as ex:
            logger.error("List reminders failed: " + str(ex))
            return []

    async def get_pending_for_user(self, user_id: int) -> List[dict]:
        """获取该用户所有未提醒的、到期的提醒"""
        if not self.pool:
            return []
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT id, content, remind_at FROM reminders
                       WHERE user_id = $1 AND is_done = FALSE AND is_notified = FALSE
                         AND remind_at <= CURRENT_TIMESTAMP
                       ORDER BY remind_at ASC""",
                    user_id
                )
                if rows:
                    # 标记为已通知
                    ids = [r["id"] for r in rows]
                    await conn.execute(
                        "UPDATE reminders SET is_notified = TRUE WHERE id = ANY($1::int[])",
                        ids
                    )
                return [
                    {
                        "id": r["id"],
                        "content": r["content"],
                        "remind_at": r["remind_at"].isoformat()
                    }
                    for r in rows
                ]
        except Exception as ex:
            logger.error("Get pending failed: " + str(ex))
            return []

    async def mark_done(self, user_id: int, reminder_id: int) -> bool:
        """标记提醒为已完成"""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE reminders SET is_done = TRUE WHERE id = $1 AND user_id = $2",
                    reminder_id, user_id
                )
                return "UPDATE 1" in result
        except Exception as ex:
            logger.error("Mark done failed: " + str(ex))
            return False

    async def delete_reminder(self, user_id: int, reminder_id: int) -> bool:
        """删除提醒"""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM reminders WHERE id = $1 AND user_id = $2",
                    reminder_id, user_id
                )
                return "DELETE 1" in result
        except Exception as ex:
            logger.error("Delete reminder failed: " + str(ex))
            return False


# 全局实例
_reminder_service = None


def get_reminder_service():
    global _reminder_service
    if _reminder_service is None:
        _reminder_service = ReminderService()
    return _reminder_service
