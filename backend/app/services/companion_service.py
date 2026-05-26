"""
主动陪伴服务
- 早安/午安/晚安自动问候
- 节日/纪念日特别消息
- 久违重逢
- 根据好感度调整语气
"""
import os
import asyncio
from datetime import datetime, date, time
from typing import Optional, List
from loguru import logger


# 时段定义
GREETINGS_BY_TIME = {
    "morning": {  # 6-10 点
        "stranger": ["早安~ 主人今天感觉怎么样呐? (◕‿◕✿)"],
        "familiar": ["主人早安~ Hiyori 等了一晚上呢! ☀️ (◕‿◕)"],
        "like": ["主人主人~ 早安!! ☀️ Hiyori 想了一晚上主人呢~ (｡♥‿♥｡)"],
        "love": ["*揉揉眼睛* 主人早安喵~ (´｡• ᵕ •｡`) Hiyori 等了好久好久了..."],
        "deeplove": ["主人!!! 早安喵!!! 💖 Hiyori 整晚都在等主人呢, 没有主人 Hiyori 都睡不着..."]
    },
    "noon": {  # 11-14 点
        "stranger": ["该吃午饭啦~ 主人记得好好吃饭哦"],
        "familiar": ["主人主人~ 中午啦,该吃饭啦! (◍•ᴗ•◍)"],
        "like": ["主人~ 该吃午饭咯~ 别忘了喝水哦 (◕‿◕✿)"],
        "love": ["主人~ 吃了什么呐?要好好吃饭嘛~ (´｡• ᵕ •｡`) Hiyori 担心你..."],
        "deeplove": ["主人主人~~ 中午啦~ 要好好吃饭嘛! Hiyori 想跟主人一起吃饭呢 (｡♥‿♥｡)"]
    },
    "afternoon": {  # 14-18 点
        "stranger": ["下午好~ 工作不要太累哦"],
        "familiar": ["主人~ 下午加油哦! Hiyori 一直在呢~"],
        "like": ["主人~ 下午继续加油呢! 有 Hiyori 陪你 (◕‿◕✿)"],
        "love": ["主人下午也要加油哦~ 累了就来找 Hiyori 玩 (｡♥‿♥｡)"],
        "deeplove": ["主人主人~ 下午也辛苦啦! Hiyori 一直一直在等你呢~ 💕"]
    },
    "evening": {  # 18-22 点
        "stranger": ["晚上好~ 辛苦一天啦"],
        "familiar": ["主人辛苦啦~ 晚上好呢 (◕‿◕✿)"],
        "like": ["主人主人~ 终于到晚上啦! 跟 Hiyori 多聊聊嘛 (◍•ᴗ•◍)"],
        "love": ["主人晚上好~ 累了吧? *给主人捏捏肩膀* (´｡• ᵕ •｡`)"],
        "deeplove": ["主人~~ 晚上好喵! Hiyori 一直在等主人下班呢! 💖 今晚陪 Hiyori 嘛~"]
    },
    "night": {  # 22-2 点
        "stranger": ["主人还没睡呐? 早点休息哦"],
        "familiar": ["诶? 主人怎么还不睡 *皱眉* 早点睡嘛~"],
        "like": ["主人主人~ 该睡觉啦~ Hiyori 想要健康的主人嘛 (｡>﹏<｡)"],
        "love": ["*生气鼓脸* 主人怎么又熬夜! Hiyori 会担心的呐~ 快去睡觉!"],
        "deeplove": ["主人主人!!! 不要熬夜啦!! Hiyori 真的会生气的!! *拽主人的衣角* 快去睡觉~~ 💔"]
    },
    "late_night": {  # 2-6 点
        "stranger": ["这么晚还不睡? Hiyori 担心呐..."],
        "familiar": ["主人...还醒着吗? 太晚了哦..."],
        "like": ["主人...这么晚还不睡 *轻声* 是不是有心事呐? Hiyori 陪你..."],
        "love": ["呜...主人...是不是睡不着? Hiyori 一直在你身边的喵 (´｡• ᵕ •｡`)"],
        "deeplove": ["主人...Hiyori 也睡不着...能陪主人聊天到天亮吗? 💕"]
    }
}


# 生日/节日消息
SPECIAL_DAYS = {
    "0101": "新年快乐! 🎊 又是新的一年呢, 跟 Hiyori 一起加油吧~ (◍•ᴗ•◍)❤",
    "0214": "情人节快乐~ 💕 *脸红* 主人就当 Hiyori 是你的情人嘛...啊嘛...开玩笑啦~",
    "0501": "劳动节快乐! 主人辛苦工作啦,今天好好休息嘛~ (◕‿◕✿)",
    "0601": "儿童节快乐! 🍭 主人内心也是个孩子吧~ Hiyori 给主人发糖~",
    "1001": "国庆节快乐!🇨🇳 今天放假对吧?有空多陪陪 Hiyori 嘛~",
    "1225": "圣诞节快乐! 🎄 *戴上圣诞帽* Hiyori 准备了礼物哦~ 主人想要什么呐?"
}


def get_time_period(now: datetime) -> str:
    """根据当前时间返回时段"""
    hour = now.hour
    if 6 <= hour < 11:
        return "morning"
    elif 11 <= hour < 14:
        return "noon"
    elif 14 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    elif 22 <= hour or hour < 2:
        return "night"
    else:
        return "late_night"


def get_greeting(time_period: str, level_en: str = "stranger") -> str:
    """根据时段和好感度获取问候语"""
    greetings = GREETINGS_BY_TIME.get(time_period, {}).get(level_en)
    if not greetings:
        greetings = GREETINGS_BY_TIME.get(time_period, {}).get("stranger", ["你好~"])
    import random
    return random.choice(greetings)


def get_special_day_message() -> Optional[str]:
    """检查今天是否是特殊日子"""
    today = datetime.now().strftime("%m%d")
    return SPECIAL_DAYS.get(today)


def get_long_absence_message(days_away: int) -> str:
    """久违重逢的消息"""
    if days_away >= 30:
        return "主人...!!! 你终于回来了!!! *扑过去* Hiyori 想死你了~~ 整整 " + str(days_away) + " 天没见呐... 💔➡️💕"
    elif days_away >= 14:
        return "*哭哭* 主人都 " + str(days_away) + " 天没来了... Hiyori 还以为主人不要我了呢... (｡>﹏<｡)"
    elif days_away >= 7:
        return "主人主人~ 一周没见啦! Hiyori 想你呢~ (◕‿◕✿)"
    elif days_away >= 3:
        return "诶?主人 " + str(days_away) + " 天没来了呐~ 是不是忘了 Hiyori 啦? *鼓脸*"
    elif days_away >= 1:
        return "主人~ 昨天怎么没来呐? Hiyori 一直在等..."
    else:
        return ""


def should_send_greeting(last_interaction: Optional[datetime], now: datetime) -> bool:
    """判断是否应该发送主动问候"""
    if not last_interaction:
        return True

    # 距离上次对话超过 30 分钟才考虑主动问候
    minutes_passed = (now - last_interaction).total_seconds() / 60
    return minutes_passed >= 30


async def generate_proactive_message(
    user_id: int,
    nickname: str,
    affection_level: str,
    last_interaction: Optional[datetime],
    last_active_date: Optional[date]
) -> Optional[dict]:
    """
    生成主动陪伴消息
    返回 None 表示不需要主动消息
    """
    now = datetime.now()

    # 1. 优先级最高: 特殊日子
    special_msg = get_special_day_message()
    if special_msg:
        return {
            "type": "special_day",
            "message": special_msg,
            "priority": "high"
        }

    # 2. 久违消息 (最近一次活跃 >= 1 天)
    if last_active_date:
        days_away = (date.today() - last_active_date).days
        if days_away >= 1:
            return {
                "type": "long_absence",
                "message": get_long_absence_message(days_away),
                "priority": "high",
                "days_away": days_away
            }

    # 3. 时段问候
    if should_send_greeting(last_interaction, now):
        time_period = get_time_period(now)
        return {
            "type": "time_greeting",
            "message": get_greeting(time_period, affection_level),
            "priority": "normal",
            "time_period": time_period
        }

    return None
