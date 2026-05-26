"""
Lord King 工具模块
- 天气 / 时间 / 计算器 / 网络搜索
- 日程提醒 (create_reminder / list_reminders)
"""
import httpx
import re
import math
from datetime import datetime
from typing import Optional
from loguru import logger


# ============ 工具定义 (给 LLM 看的) ============

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather and forecast for a city. Use when user asks about weather, temperature, rain, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name in Chinese or English, e.g. '上海', 'Shanghai'"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get current date and time. Use when user asks what time/date it is now.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "default": "Asia/Shanghai"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Calculate math expression. Use for arithmetic, percentages, conversions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, e.g. '365 * 24', 'sqrt(144)'"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search web for current information. Use for news, recent events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a reminder/schedule for the user. Use when user says '提醒我...', '帮我设置一个...', '到时候叫我...', or wants to schedule something. The system will parse natural language time like '明天9点', '10分钟后', '下午3点半'. After calling, tell user in Hiyori cute voice that the reminder is set.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The complete user request in Chinese, e.g. '明天上午9点提醒我开会', '10分钟后提醒我喝水', '后天晚上8点和小王吃饭'"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List all pending reminders for the user. Use when user asks '我的日程', '有什么提醒', '看下我的待办', etc.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


# ============ 工具实现 ============

async def get_weather(city: str, **kwargs) -> str:
    """查询天气 - wttr.in"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"https://wttr.in/{city}?format=j1&lang=zh"
            response = await client.get(url)
            if response.status_code != 200:
                return f"无法查询 {city} 的天气"
            data = response.json()
            current = data["current_condition"][0]
            nearest = data["nearest_area"][0]
            location = nearest["areaName"][0]["value"]
            temp_c = current["temp_C"]
            feels_like = current["FeelsLikeC"]
            desc = current["lang_zh"][0]["value"] if "lang_zh" in current else current["weatherDesc"][0]["value"]
            humidity = current["humidity"]
            wind_speed = current["windspeedKmph"]
            wind_dir = current["winddir16Point"]
            forecast_lines = []
            for day in data["weather"][:3]:
                date_str = day["date"]
                max_t = day["maxtempC"]
                min_t = day["mintempC"]
                day_desc = day["hourly"][4]["lang_zh"][0]["value"] if "lang_zh" in day["hourly"][4] else day["hourly"][4]["weatherDesc"][0]["value"]
                forecast_lines.append(f"{date_str}: {day_desc}, {min_t}~{max_t}度")
            return (
                f"{location}天气: {desc}\n"
                f"温度: {temp_c}度 (体感 {feels_like}度)\n"
                f"湿度: {humidity}%\n"
                f"风向: {wind_dir}, 风速 {wind_speed} km/h\n"
                f"\n未来 3 天预报:\n" + "\n".join(forecast_lines)
            )
    except Exception as e:
        logger.error("Weather query failed: " + str(e))
        return f"查询天气出错: {str(e)}"


def get_current_time(timezone: str = "Asia/Shanghai", **kwargs) -> str:
    """获取当前时间"""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    weekday_zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    return now.strftime("%Y年%m月%d日 ") + weekday_zh + now.strftime(" %H:%M:%S")


def calculate(expression: str, **kwargs) -> str:
    """安全的数学计算"""
    try:
        expr = expression.strip().replace("×", "*").replace("÷", "/").replace("^", "**")
        safe_namespace = {
            "__builtins__": {},
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "log10": math.log10, "exp": math.exp,
            "pi": math.pi, "e": math.e, "abs": abs, "pow": pow,
            "ceil": math.ceil, "floor": math.floor, "round": round,
        }
        result = eval(expr, safe_namespace)
        if isinstance(result, float):
            if result.is_integer():
                result = int(result)
            else:
                result = round(result, 6)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算出错: {str(e)}"


async def web_search(query: str, **kwargs) -> str:
    """DuckDuckGo + Wikipedia"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = "https://api.duckduckgo.com/"
            params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
            response = await client.get(url, params=params)
            data = response.json()
            results = []
            if data.get("AbstractText"):
                results.append("摘要: " + data["AbstractText"])
            if data.get("Definition"):
                results.append("定义: " + data["Definition"])
            related = data.get("RelatedTopics", [])
            if related:
                for item in related[:3]:
                    if isinstance(item, dict) and item.get("Text"):
                        results.append("- " + item["Text"][:200])
            if results:
                return "\n".join(results)
            # 备选 Wikipedia
            try:
                url2 = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{query}"
                r = await client.get(url2, headers={"User-Agent": "LordKing/1.0"})
                if r.status_code == 200:
                    extract = r.json().get("extract", "")
                    if extract:
                        return f"维基百科: {extract[:500]}"
            except Exception:
                pass
            return f"没有找到关于 '{query}' 的搜索结果"
    except Exception as e:
        logger.error("Web search failed: " + str(e))
        return f"搜索出错: {str(e)}"


# ============ 日程提醒工具 (新增) ============

async def create_reminder(text: str, user_id: int = None, **kwargs) -> str:
    """
    创建提醒 - 智能解析自然语言时间
    """
    if not user_id:
        return "无法识别用户身份,请先登录"

    try:
        from app.services.reminder_service import get_reminder_service
        reminder_service = get_reminder_service()

        # 解析时间
        remind_at = reminder_service.parse_time(text)
        if not remind_at:
            return "我没听清楚时间呐~ 主人能说得清楚一点吗? 比如'明天9点'或'10分钟后'"

        # 解析内容
        content = reminder_service.extract_content(text)

        # 创建
        rid = await reminder_service.create_reminder(user_id, content, remind_at)
        if not rid:
            return "提醒创建失败了喵..."

        # 返回友好的描述
        now = datetime.now()
        delta = remind_at - now
        if delta.total_seconds() < 0:
            time_desc = "已经过去的时间(可能解析错误)"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            time_desc = f"{minutes}分钟后"
        elif delta.days == 0:
            time_desc = "今天 " + remind_at.strftime("%H:%M")
        elif delta.days == 1:
            time_desc = "明天 " + remind_at.strftime("%H:%M")
        elif delta.days == 2:
            time_desc = "后天 " + remind_at.strftime("%H:%M")
        elif delta.days < 7:
            time_desc = f"{delta.days}天后 " + remind_at.strftime("%H:%M")
        else:
            time_desc = remind_at.strftime("%Y-%m-%d %H:%M")

        return f"已记下提醒: {time_desc} - {content} (id={rid})"

    except Exception as e:
        logger.error("Create reminder failed: " + str(e))
        return "创建提醒出错: " + str(e)


async def list_reminders(user_id: int = None, **kwargs) -> str:
    """列出当前用户的所有提醒"""
    if not user_id:
        return "无法识别用户身份"

    try:
        from app.services.reminder_service import get_reminder_service
        reminder_service = get_reminder_service()
        reminders = await reminder_service.list_reminders(user_id)

        if not reminders:
            return "主人当前没有任何提醒哦~"

        lines = ["主人的提醒列表:"]
        now = datetime.now()
        for r in reminders[:10]:
            try:
                remind_at = datetime.fromisoformat(r["remind_at"])
                delta = remind_at - now
                if delta.total_seconds() < 0:
                    status = "(已过期)"
                elif delta.total_seconds() < 3600:
                    minutes = int(delta.total_seconds() / 60)
                    status = f"({minutes}分钟后)"
                elif delta.days == 0:
                    status = "(今天 " + remind_at.strftime("%H:%M") + ")"
                elif delta.days == 1:
                    status = "(明天 " + remind_at.strftime("%H:%M") + ")"
                else:
                    status = "(" + remind_at.strftime("%m-%d %H:%M") + ")"
                lines.append(f"- {r['content']} {status}")
            except Exception:
                lines.append(f"- {r['content']} (时间解析错误)")

        if len(reminders) > 10:
            lines.append(f"... 还有 {len(reminders) - 10} 条")

        return "\n".join(lines)

    except Exception as e:
        logger.error("List reminders failed: " + str(e))
        return "获取提醒列表出错: " + str(e)


# ============ 工具调度器 ============

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "get_current_time": get_current_time,
    "calculate": calculate,
    "web_search": web_search,
    "create_reminder": create_reminder,
    "list_reminders": list_reminders,
}


async def execute_tool(name: str, arguments: dict, user_id: int = None) -> str:
    """
    执行工具调用
    user_id 是必要参数,用于身份相关的工具(如 reminder)
    """
    if name not in TOOL_REGISTRY:
        return f"未知工具: {name}"

    func = TOOL_REGISTRY[name]
    try:
        import inspect
        # 自动注入 user_id 到 kwargs
        if user_id is not None:
            arguments["user_id"] = user_id

        if inspect.iscoroutinefunction(func):
            result = await func(**arguments)
        else:
            result = func(**arguments)

        logger.info(f"Tool [{name}] executed, result length: {len(str(result))}")
        return str(result)

    except TypeError as e:
        # 如果工具不接受某些参数,过滤掉再试
        logger.warning(f"Tool [{name}] TypeError, retrying without extra args: {e}")
        sig = inspect.signature(func)
        valid_args = {k: v for k, v in arguments.items() if k in sig.parameters}
        try:
            if inspect.iscoroutinefunction(func):
                return await func(**valid_args)
            else:
                return func(**valid_args)
        except Exception as e2:
            return f"工具执行出错: {str(e2)}"
    except Exception as e:
        logger.error(f"Tool [{name}] failed: {e}")
        return f"工具执行出错: {str(e)}"
