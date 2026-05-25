"""
Nexus AI 工具模块
提供天气、时间、计算器、搜索等能力
"""
import httpx
import re
import math
from datetime import datetime
from typing import Optional
from loguru import logger


# ============ 工具定义(给 LLM 看的) ============

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
                        "description": "City name in Chinese or English, e.g. '上海', 'Shanghai', '北京'"
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
            "description": "Get current date and time. Use when user asks what time/date it is now, day of week, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone, default is China (Asia/Shanghai)",
                        "default": "Asia/Shanghai"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Calculate math expression. Use for arithmetic, percentages, conversions, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to calculate, e.g. '365 * 24', 'sqrt(144)', '15 / 100 * 2000'"
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
            "description": "Search the web for current information. Use for news, recent events, facts you may not know.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in Chinese or English"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ============ 工具实现 ============

async def get_weather(city: str) -> str:
    """查询天气 - 用 wttr.in 免费 API"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # wttr.in 支持中文城市名
            url = f"https://wttr.in/{city}?format=j1&lang=zh"
            response = await client.get(url)
            
            if response.status_code != 200:
                return f"无法查询 {city} 的天气，请稍后再试"
            
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
            
            # 未来 3 天预报
            forecast_lines = []
            for day in data["weather"][:3]:
                date = day["date"]
                max_t = day["maxtempC"]
                min_t = day["mintempC"]
                day_desc = day["hourly"][4]["lang_zh"][0]["value"] if "lang_zh" in day["hourly"][4] else day["hourly"][4]["weatherDesc"][0]["value"]
                forecast_lines.append(f"{date}: {day_desc}, {min_t}~{max_t}度")
            
            result = (
                f"{location}天气：{desc}\n"
                f"温度: {temp_c}度（体感 {feels_like}度）\n"
                f"湿度: {humidity}%\n"
                f"风向: {wind_dir}，风速 {wind_speed} km/h\n"
                f"\n未来 3 天预报：\n" + "\n".join(forecast_lines)
            )
            return result
            
    except Exception as e:
        logger.error("Weather query failed: " + str(e))
        return f"查询天气出错: {str(e)}"


def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """获取当前时间"""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        weekday_zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
        return now.strftime("%Y年%m月%d日 ") + weekday_zh + now.strftime(" %H:%M:%S")
    except Exception as e:
        # 降级到不带时区
        now = datetime.now()
        weekday_zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
        return now.strftime("%Y年%m月%d日 ") + weekday_zh + now.strftime(" %H:%M:%S")


def calculate(expression: str) -> str:
    """安全的数学计算"""
    try:
        # 只允许安全字符
        safe_chars = set("0123456789+-*/().,% ")
        safe_funcs = ["sqrt", "sin", "cos", "tan", "log", "log10", "exp", "pi", "e", "abs", "pow", "ceil", "floor"]
        
        # 清理表达式
        expr = expression.strip()
        
        # 替换一些常见写法
        expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
        
        # 提供安全的命名空间
        safe_namespace = {
            "__builtins__": {},
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "pi": math.pi,
            "e": math.e,
            "abs": abs,
            "pow": pow,
            "ceil": math.ceil,
            "floor": math.floor,
            "round": round,
        }
        
        result = eval(expr, safe_namespace)
        
        # 格式化结果
        if isinstance(result, float):
            if result.is_integer():
                result = int(result)
            else:
                result = round(result, 6)
        
        return f"{expression} = {result}"
        
    except Exception as e:
        return f"计算出错: {str(e)}"


async def web_search(query: str) -> str:
    """网络搜索 - 用 DuckDuckGo Instant Answer API(免费)"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 用 DuckDuckGo 免费 API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            }
            response = await client.get(url, params=params)
            data = response.json()
            
            results = []
            
            # 直接答案
            if data.get("AbstractText"):
                results.append("摘要: " + data["AbstractText"])
            
            # 定义/概念
            if data.get("Definition"):
                results.append("定义: " + data["Definition"])
            
            # 相关主题
            related = data.get("RelatedTopics", [])
            if related:
                for item in related[:3]:
                    if isinstance(item, dict) and item.get("Text"):
                        results.append("- " + item["Text"][:200])
            
            if results:
                return "\n".join(results)
            
            # 如果 DuckDuckGo 没结果,尝试 Wikipedia
            return await _wikipedia_search(query)
            
    except Exception as e:
        logger.error("Web search failed: " + str(e))
        return f"搜索出错: {str(e)}"


async def _wikipedia_search(query: str) -> str:
    """Wikipedia 中文搜索作为备选"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Wikipedia REST API
            url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{query}"
            response = await client.get(url, headers={"User-Agent": "Nexus-AI/1.0"})
            
            if response.status_code == 200:
                data = response.json()
                extract = data.get("extract", "")
                if extract:
                    return f"维基百科: {extract[:500]}"
            
            return f"没有找到关于'{query}'的搜索结果"
            
    except Exception as e:
        return f"搜索失败: {str(e)}"


# ============ 工具调度器 ============

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "get_current_time": get_current_time,
    "calculate": calculate,
    "web_search": web_search,
}


async def execute_tool(name: str, arguments: dict) -> str:
    """执行工具调用"""
    if name not in TOOL_REGISTRY:
        return f"未知工具: {name}"
    
    func = TOOL_REGISTRY[name]
    
    try:
        import inspect
        # 判断是异步还是同步
        if inspect.iscoroutinefunction(func):
            result = await func(**arguments)
        else:
            result = func(**arguments)
        
        logger.info(f"Tool [{name}] executed, result length: {len(str(result))}")
        return str(result)
        
    except Exception as e:
        logger.error(f"Tool [{name}] failed: {e}")
        return f"工具执行出错: {str(e)}"
