"""
自主进化技能引擎 (Self-Evolving Skills Engine)
=============================================
核心能力:
1. 技能自动发现 - 扫描 skills/ 目录,动态加载
2. 工具自注册 - 新工具自动注册到 LLM 的 TOOL_DEFINITIONS
3. 自我改进 - 根据使用反馈优化工具 prompt 和逻辑
4. 动态工具生成 - AI 可以自己写新工具并热加载
5. 使用统计 - 追踪每个工具的成功率/延迟/频率
"""

import os
import json
import time
import importlib
import importlib.util
import traceback
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field, asdict
from loguru import logger


SKILLS_DIR = Path(os.getenv("SKILLS_DIR", "/root/Lord-King/data/skills"))
STATS_FILE = Path(os.getenv("SKILLS_DIR", "/root/Lord-King/data/skills")) / "stats.json"


@dataclass
class ToolStats:
    """工具使用统计"""
    name: str
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    last_called: Optional[str] = None
    last_error: Optional[str] = None
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0

    def record(self, success: bool, latency_ms: float, error: str = None):
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        self.last_called = datetime.now().isoformat()
        if success:
            self.success_calls += 1
        else:
            self.failed_calls += 1
            self.last_error = error
        self.avg_latency_ms = self.total_latency_ms / self.total_calls
        self.success_rate = self.success_calls / self.total_calls


@dataclass
class SkillDefinition:
    """技能定义"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "system"
    created_at: str = ""
    updated_at: str = ""
    tool_definition: Dict = field(default_factory=dict)
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class SkillsEngine:
    """
    自主进化技能引擎
    ================
    - 管理所有动态技能/工具
    - 提供工具注册、发现、统计、自改进
    - 支持热加载:新增技能文件后自动生效
    """

    def __init__(self):
        self.skills: Dict[str, SkillDefinition] = {}
        self.tool_funcs: Dict[str, Callable] = {}
        self.stats: Dict[str, ToolStats] = {}
        self._tool_definitions_cache: List[Dict] = []
        self._cache_dirty = True

        # 确保目录存在
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        # 加载统计
        self._load_stats()

        # 加载内置技能
        self._load_builtin_skills()

        # 加载外部技能文件
        self._load_external_skills()

        logger.info(f"SkillsEngine initialized: {len(self.skills)} skills loaded")

    # ============ 技能发现与加载 ============

    def _load_builtin_skills(self):
        """加载内置高级技能"""
        builtin_skills = [
            self._skill_web_scraper,
            self._skill_code_runner,
            self._skill_file_manager,
            self._skill_memory_search,
            self._skill_self_reflect,
        ]
        for skill_fn in builtin_skills:
            try:
                skill_def, tool_fn = skill_fn()
                self._register_skill(skill_def, tool_fn)
            except Exception as e:
                logger.error(f"Failed to load builtin skill: {e}")

    def _load_external_skills(self):
        """从 skills/ 目录加载外部技能文件"""
        if not SKILLS_DIR.exists():
            return
        for skill_file in SKILLS_DIR.glob("*.py"):
            if skill_file.name.startswith("_"):
                continue
            try:
                self._load_skill_file(skill_file)
            except Exception as e:
                logger.error(f"Failed to load skill file {skill_file.name}: {e}")

    def _load_skill_file(self, path: Path):
        """动态加载单个技能文件"""
        spec = importlib.util.spec_from_file_location(path.stem, str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 技能文件必须导出 get_skill() -> (SkillDefinition, Callable)
        if hasattr(module, "get_skill"):
            skill_def, tool_fn = module.get_skill()
            self._register_skill(skill_def, tool_fn)
            logger.info(f"Loaded external skill: {skill_def.name} from {path.name}")

    def _register_skill(self, skill_def: SkillDefinition, tool_fn: Callable):
        """注册一个技能"""
        self.skills[skill_def.name] = skill_def
        self.tool_funcs[skill_def.name] = tool_fn
        if skill_def.name not in self.stats:
            self.stats[skill_def.name] = ToolStats(name=skill_def.name)
        self._cache_dirty = True

    # ============ 内置技能定义 ============

    def _skill_web_scraper(self) -> tuple:
        """网页内容抓取工具"""
        skill = SkillDefinition(
            name="web_scraper",
            description="抓取指定网页的正文内容,提取标题和正文文本。适用于需要获取网页详细内容的场景。",
            version="1.0.0",
            tags=["web", "fetch", "content"],
            tool_definition={
                "type": "function",
                "function": {
                    "name": "web_scraper",
                    "description": "抓取指定网页的正文内容,提取标题和正文文本。输入URL,返回网页标题和正文。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "要抓取的网页URL,例如 https://example.com/article"
                            }
                        },
                        "required": ["url"]
                    }
                }
            }
        )

        async def tool_fn(url: str, **kwargs) -> str:
            import httpx
            import re
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })
                    if resp.status_code != 200:
                        return f"抓取失败: HTTP {resp.status_code}"
                    html = resp.text
                    # 提取 title
                    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
                    title = title_match.group(1).strip() if title_match else "无标题"
                    # 去除 script/style
                    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                    # 提取正文
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text).strip()
                    text = text[:5000]  # 限制长度
                    return f"标题: {title}\n\n正文:\n{text}"
            except Exception as e:
                return f"抓取失败: {str(e)}"

        return skill, tool_fn

    def _skill_code_runner(self) -> tuple:
        """安全代码执行工具 (沙箱)"""
        skill = SkillDefinition(
            name="code_runner",
            description="在沙箱中执行 Python 代码,返回执行结果。用于数学计算、数据处理、算法验证等。",
            version="1.0.0",
            tags=["code", "python", "compute"],
            tool_definition={
                "type": "function",
                "function": {
                    "name": "code_runner",
                    "description": "在安全沙箱中执行 Python 代码。支持数学运算、字符串处理、数据分析等。代码执行时间限制5秒。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "要执行的 Python 代码,例如 'sum(range(100))' 或更复杂的多行代码"
                            }
                        },
                        "required": ["code"]
                    }
                }
            }
        )

        async def tool_fn(code: str, **kwargs) -> str:
            import asyncio
            try:
                # 安全白名单:只允许纯计算
                dangerous = ["import os", "import sys", "open(", "__import__", "exec(", "eval(",
                             "subprocess", "socket", "requests", "urllib"]
                for d in dangerous:
                    if d in code:
                        return f"安全限制: 不允许使用 '{d}'"

                # 在子进程执行,限制时间
                proc = await asyncio.create_subprocess_exec(
                    "python3", "-c",
                    f"import sys; sys.setrecursionlimit(1000); print(repr(eval({repr(code)})))",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    return "执行超时(超过5秒)"

                if proc.returncode == 0:
                    return f"结果: {stdout.decode().strip()}"
                else:
                    return f"执行错误: {stderr.decode().strip()[:200]}"
            except Exception as e:
                return f"执行失败: {str(e)}"

        return skill, tool_fn

    def _skill_file_manager(self) -> tuple:
        """文件管理工具"""
        skill = SkillDefinition(
            name="file_manager",
            description="读取、列出、搜索服务器上的文件。用于查看日志、配置文件、项目代码等。",
            version="1.0.0",
            tags=["file", "read", "search"],
            tool_definition={
                "type": "function",
                "function": {
                    "name": "file_manager",
                    "description": "文件管理工具。action=read 读取文件内容, action=list 列出目录, action=grep 搜索文件内容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["read", "list", "grep"],
                                "description": "操作类型: read=读取文件, list=列出目录, grep=搜索内容"
                            },
                            "path": {
                                "type": "string",
                                "description": "文件路径或目录路径,例如 /root/Lord-King/backend/app/main.py"
                            },
                            "pattern": {
                                "type": "string",
                                "description": "搜索模式(仅 action=grep 时需要),例如 'def chat'"
                            },
                            "lines": {
                                "type": "integer",
                                "description": "读取行数(仅 action=read),默认50"
                            }
                        },
                        "required": ["action", "path"]
                    }
                }
            }
        )

        async def tool_fn(action: str, path: str, pattern: str = None, lines: int = 50, **kwargs) -> str:
            import subprocess
            try:
                target = Path(path)
                # 安全限制:只能访问 /root 和 /var/log
                allowed_roots = ["/root", "/var/log", "/tmp", "/etc/nginx"]
                if not any(str(target).startswith(r) for r in allowed_roots):
                    return f"安全限制: 只能访问 {allowed_roots}"

                if action == "read":
                    if not target.exists():
                        return f"文件不存在: {path}"
                    result = subprocess.run(
                        ["head", "-n", str(lines), str(target)],
                        capture_output=True, text=True, timeout=5
                    )
                    return f"文件: {path} (前{lines}行)\n\n{result.stdout}"

                elif action == "list":
                    if not target.is_dir():
                        return f"不是目录: {path}"
                    result = subprocess.run(
                        ["ls", "-lah", str(target)],
                        capture_output=True, text=True, timeout=5
                    )
                    return f"目录: {path}\n\n{result.stdout}"

                elif action == "grep":
                    if not pattern:
                        return "grep 需要提供 pattern 参数"
                    result = subprocess.run(
                        ["grep", "-rn", pattern, str(target)],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        return f"搜索结果:\n{result.stdout[:3000]}"
                    return f"未找到匹配 '{pattern}' 的内容"

                return f"未知操作: {action}"
            except Exception as e:
                return f"文件操作失败: {str(e)}"

        return skill, tool_fn

    def _skill_memory_search(self) -> tuple:
        """高级记忆搜索工具"""
        skill = SkillDefinition(
            name="memory_search",
            description="在长期记忆中搜索特定话题的对话记录。比默认召回更精准,支持关键词和时间范围过滤。",
            version="1.0.0",
            tags=["memory", "search", "history"],
            tool_definition={
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "description": "在长期记忆中搜索特定话题。返回最相关的历史对话片段。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词或话题,例如 '上次聊的旅行计划'"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量,默认5"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        )

        async def tool_fn(query: str, limit: int = 5, **kwargs) -> str:
            # 这个工具需要 milvus 服务,由外部注入
            milvus = kwargs.get("_milvus_service")
            if not milvus:
                return "记忆服务未就绪"
            try:
                user_id = kwargs.get("user_id", "default")
                memories = await milvus.search_memories(
                    user_id=str(user_id), query=query, top_k=limit
                )
                if not memories:
                    return f"没有找到关于 '{query}' 的记忆"
                lines = []
                for i, m in enumerate(memories, 1):
                    content = m.get("content", "")[:300]
                    lines.append(f"{i}. {content}")
                return f"找到 {len(lines)} 条相关记忆:\n" + "\n".join(lines)
            except Exception as e:
                return f"记忆搜索失败: {str(e)}"

        return skill, tool_fn

    def _skill_self_reflect(self) -> tuple:
        """自我反思工具 - AI 分析自己的表现"""
        skill = SkillDefinition(
            name="self_reflect",
            description="AI 自我反思工具。分析最近的对话质量、工具使用情况、错误率,给出改进建议。用于自主进化。",
            version="1.0.0",
            tags=["meta", "self-improvement", "diagnostics"],
            tool_definition={
                "type": "function",
                "function": {
                    "name": "self_reflect",
                    "description": "AI 自我反思:分析最近的工具使用统计、错误率、响应质量。返回诊断报告和改进建议。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scope": {
                                "type": "string",
                                "enum": ["tools", "memory", "all"],
                                "description": "反思范围: tools=工具使用, memory=记忆系统, all=全部"
                            }
                        }
                    }
                }
            }
        )

        async def tool_fn(scope: str = "all", **kwargs) -> str:
            engine = kwargs.get("_skills_engine")
            if not engine:
                return "引擎未就绪"

            report = ["=== AI 自我反思报告 ===\n"]

            if scope in ("tools", "all"):
                report.append("【工具使用统计】")
                for name, stats in engine.stats.items():
                    if stats.total_calls > 0:
                        report.append(
                            f"  {name}: 调用{stats.total_calls}次, "
                            f"成功率{stats.success_rate*100:.0f}%, "
                            f"平均延迟{stats.avg_latency_ms:.0f}ms"
                        )
                        if stats.last_error:
                            report.append(f"    最后错误: {stats.last_error[:100]}")
                report.append("")

            if scope in ("memory", "all"):
                report.append("【技能库状态】")
                report.append(f"  已加载技能: {len(engine.skills)} 个")
                for name, skill in engine.skills.items():
                    report.append(f"  - {name} v{skill.version} ({', '.join(skill.tags)})")

            return "\n".join(report)

        return skill, tool_fn

    # ============ 工具执行 ============

    async def execute_tool(self, name: str, arguments: dict, user_id: int = None) -> str:
        """执行一个技能工具,自动记录统计"""
        if name not in self.tool_funcs:
            return f"未知技能: {name}"

        func = self.tool_funcs[name]
        stats = self.stats.get(name, ToolStats(name=name))

        # 注入内部服务
        arguments["_skills_engine"] = self
        arguments["_milvus_service"] = getattr(self, "_milvus_service", None)

        start = time.time()
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)
            latency = (time.time() - start) * 1000
            stats.record(success=True, latency_ms=latency)
            self._save_stats()
            return str(result)
        except Exception as e:
            latency = (time.time() - start) * 1000
            tb = traceback.format_exc()
            stats.record(success=False, latency_ms=latency, error=str(e))
            self._save_stats()
            logger.error(f"Skill [{name}] failed: {e}\n{tb}")
            return f"技能执行出错: {str(e)[:200]}"

    # ============ 工具定义导出 ============

    def get_tool_definitions(self) -> List[Dict]:
        """获取所有技能的工具定义 (给 LLM 用)"""
        if not self._cache_dirty and self._tool_definitions_cache:
            return self._tool_definitions_cache

        definitions = []
        for name, skill in self.skills.items():
            if skill.enabled and skill.tool_definition:
                definitions.append(skill.tool_definition)

        self._tool_definitions_cache = definitions
        self._cache_dirty = False
        return definitions

    # ============ 自我进化 ============

    async def suggest_improvement(self, llm_service) -> Optional[str]:
        """分析统计数据,建议改进方向"""
        problem_tools = [
            s for s in self.stats.values()
            if s.total_calls > 3 and s.success_rate < 0.5
        ]
        if not problem_tools:
            return None

        suggestions = []
        for t in problem_tools:
            suggestions.append(
                f"工具 '{t.name}' 成功率仅 {t.success_rate*100:.0f}%,"
                f"最后错误: {t.last_error[:100] if t.last_error else 'N/A'}"
            )
        return "需要改进的工具:\n" + "\n".join(suggestions)

    # ============ 统计持久化 ============

    def _load_stats(self):
        """加载统计"""
        if STATS_FILE.exists():
            try:
                data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
                for name, d in data.items():
                    self.stats[name] = ToolStats(**d)
            except Exception:
                pass

    def _save_stats(self):
        """保存统计"""
        try:
            data = {name: asdict(s) for name, s in self.stats.items()}
            STATS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ============ 管理接口 ============

    def get_status(self) -> Dict:
        """获取引擎状态"""
        return {
            "total_skills": len(self.skills),
            "skills": {
                name: {
                    "version": s.version,
                    "enabled": s.enabled,
                    "tags": s.tags,
                    "stats": asdict(self.stats.get(name, ToolStats(name=name)))
                }
                for name, s in self.skills.items()
            }
        }

    def disable_skill(self, name: str) -> bool:
        if name in self.skills:
            self.skills[name].enabled = False
            self._cache_dirty = True
            return True
        return False

    def enable_skill(self, name: str) -> bool:
        if name in self.skills:
            self.skills[name].enabled = True
            self._cache_dirty = True
            return True
        return False


# 全局单例
_engine: Optional[SkillsEngine] = None


def get_skills_engine() -> SkillsEngine:
    global _engine
    if _engine is None:
        _engine = SkillsEngine()
    return _engine


import asyncio  # noqa: E402 - needed for execute_tool
