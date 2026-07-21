"""
Lord-King Autonomous Evolution Daemon
Background process for continuous self-improvement.
"""
import os, sys, json, time, asyncio, re
from pathlib import Path
from datetime import datetime
from loguru import logger

sys.path.insert(0, "/app")
os.chdir("/app")


class EvolutionDaemon:
    def __init__(self):
        self.skills_engine = None
        self.llm_service = None
        self.milvus_service = None
        self.reflect_interval = int(os.getenv("EVOLVE_REFLECT_INTERVAL", "1800"))
        self.memory_interval = int(os.getenv("EVOLVE_MEMORY_INTERVAL", "3600"))
        self.search_interval = int(os.getenv("EVOLVE_SEARCH_INTERVAL", "7200"))
        self.repair_interval = int(os.getenv("EVOLVE_REPAIR_INTERVAL", "900"))
        self.last_reflect = None
        self.last_memory = None
        self.last_search = None
        self.last_repair = None
        self.reflection_count = 0
        self.tools_generated = 0
        self.errors_fixed = 0
        self.evolution_log = []
        self.tech_feeds = [
            ("Hacker News", "https://news.ycombinator.com/rss"),
            ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ]

    def _log(self, category, message, data=None):
        event = {"time": datetime.now().isoformat(), "category": category, "message": message, "data": data or {}}
        self.evolution_log.append(event)
        if len(self.evolution_log) > 100:
            self.evolution_log = self.evolution_log[-100:]
        logger.info(f"[Evolve] [{category}] {message}")

    async def initialize(self):
        try:
            from app.services.skills import get_skills_engine
            self.skills_engine = get_skills_engine()
            self._log("init", f"SkillsEngine ready: {len(self.skills_engine.skills)} skills")
        except Exception as e:
            self._log("error", f"SkillsEngine init failed: {e}")
        try:
            from app.services.llm_service import get_llm_service
            self.llm_service = get_llm_service()
            self._log("init", "LLM service ready")
        except Exception as e:
            self._log("error", f"LLM service init failed: {e}")

    async def reflect(self):
        self._log("reflect", "Starting self-reflection...")
        self.reflection_count += 1
        try:
            stats = self.skills_engine.get_status() if self.skills_engine else {}
            problems = []
            for name, info in stats.get("skills", {}).items():
                ts = info.get("stats", {})
                if ts.get("total_calls", 0) > 3 and ts.get("success_rate", 1.0) < 0.5:
                    problems.append({"name": name, "success_rate": ts["success_rate"], "last_error": ts.get("last_error", "")})
            if problems:
                self._log("reflect", f"Found {len(problems)} problematic tools", problems)
                for p in problems:
                    await self._try_fix_tool(p["name"], p["last_error"])
            else:
                self._log("reflect", "All tools healthy!")
            await self._detect_capability_gaps()
        except Exception as e:
            self._log("error", f"Reflection failed: {e}")
        self.last_reflect = datetime.now()

    async def _detect_capability_gaps(self):
        if not self.skills_engine or not self.llm_service:
            return
        existing_tags = set()
        for skill in self.skills_engine.skills.values():
            existing_tags.update(skill.tags)
        desired = {"web": "web scraping", "search": "real-time search", "compute": "math", "file": "file ops", "memory": "memory", "language": "translation", "code": "code exec", "image": "vision", "calendar": "calendar", "news": "news", "weather": "weather"}
        missing = [(t, d) for t, d in desired.items() if t not in existing_tags]
        if missing:
            self._log("reflect", f"Capability gaps: {len(missing)}", {"missing": [m[0] for m in missing]})
        else:
            self._log("reflect", "All core capabilities covered!")

    async def check_and_repair(self):
        if not self.skills_engine:
            return
        repaired = 0
        for name, stats in self.skills_engine.stats.items():
            if stats.total_calls > 2 and stats.success_rate < 0.3 and stats.last_error:
                self._log("repair", f"Tool '{name}' low success ({stats.success_rate:.0%}), repairing")
                await self._try_fix_tool(name, stats.last_error)
                repaired += 1
        if repaired:
            self._log("repair", f"Attempted repair on {repaired} tools")
            self.errors_fixed += repaired
        self.last_repair = datetime.now()

    async def _try_fix_tool(self, tool_name, last_error):
        if not self.llm_service or not self.skills_engine or tool_name not in self.skills_engine.skills:
            return
        skill = self.skills_engine.skills[tool_name]
        prompt = "Debug this Python tool that keeps failing.\n\n"
        prompt += "Tool: " + tool_name + "\n"
        prompt += "Description: " + str(skill.description) + "\n"
        prompt += "Error: " + str(last_error[:500]) + "\n\n"
        prompt += "Output JSON with fields: cause, fix, needs_regenerate"
        try:
            response = await self.llm_service.chat(message=prompt, system_prompt="Debug expert. Output only JSON.")
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                analysis = json.loads(match.group())
                self._log("repair", "Analysis for " + tool_name, analysis)
        except Exception as e:
            self._log("error", "Fix analysis failed: " + str(e))

            self._log("error", f"Fix analysis failed: {e}")

    async def search_and_integrate(self):
        if not self.llm_service:
            return
        self._log("search", "Scanning for new technologies...")
        try:
            headlines = await self._fetch_tech_news()
            if not headlines:
                return
            prompt = f"""AI tech analyst. News headlines:
{json.dumps(headlines[:15], ensure_ascii=False, indent=2)}

Existing tools: {list(self.skills_engine.skills.keys()) if self.skills_engine else []}

Output JSON array: [{{"title": "...", "tool_name": "...", "description": "...", "priority": "high/medium/low"}}]"""
            response = await self.llm_service.chat(message=prompt, system_prompt="Tech analyst. Output only JSON array.")
            match = re.search(r"\[[\s\S]*\]", response)
            if match:
                suggestions = json.loads(match.group())
                if suggestions:
                    self._log("search", f"Found {len(suggestions)} potential integrations", suggestions)
        except Exception as e:
            self._log("error", f"Tech search failed: {e}")
        self.last_search = datetime.now()

    async def _fetch_tech_news(self):
        import httpx
        headlines = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for name, url in self.tech_feeds[:2]:
                    try:
                        resp = await client.get(url, headers={"User-Agent": "LordKing/6.0"})
                        if resp.status_code == 200:
                            titles = re.findall(r"<title[^>]*>(.*?)</title>", resp.text[:5000])
                            for t in titles[1:6]:
                                clean = re.sub(r"<!\[CDATA\[|\]\]>", "", t).strip()
                                if clean and len(clean) < 200:
                                    headlines.append(clean)
                    except Exception:
                        continue
        except Exception:
            pass
        return headlines

    async def consolidate_memory(self):
        if not self.milvus_service:
            return
        self._log("memory", "Starting memory consolidation...")
        self.last_memory = datetime.now()

    async def run(self):
        self._log("daemon", "Evolution Daemon starting...", {
            "reflect_interval": self.reflect_interval,
            "repair_interval": self.repair_interval,
            "search_interval": self.search_interval,
            "memory_interval": self.memory_interval,
        })
        await self.initialize()
        await self.reflect()
        while True:
            try:
                now = datetime.now()
                if self.last_repair is None or (now - self.last_repair).seconds >= self.repair_interval:
                    await self.check_and_repair()
                if self.last_reflect is None or (now - self.last_reflect).seconds >= self.reflect_interval:
                    await self.reflect()
                if self.last_memory is None or (now - self.last_memory).seconds >= self.memory_interval:
                    await self.consolidate_memory()
                if self.last_search is None or (now - self.last_search).seconds >= self.search_interval:
                    await self.search_and_integrate()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                self._log("daemon", "Daemon stopped")
                break
            except Exception as e:
                self._log("error", f"Main loop error: {e}")
                await asyncio.sleep(60)

    def get_status(self):
        return {
            "running": True,
            "reflection_count": self.reflection_count,
            "tools_generated": self.tools_generated,
            "errors_fixed": self.errors_fixed,
            "last_reflect": self.last_reflect.isoformat() if self.last_reflect else None,
            "last_repair": self.last_repair.isoformat() if self.last_repair else None,
            "last_search": self.last_search.isoformat() if self.last_search else None,
            "last_memory": self.last_memory.isoformat() if self.last_memory else None,
            "recent_events": self.evolution_log[-10:],
        }


_daemon = None

def get_evolution_daemon():
    global _daemon
    if _daemon is None:
        _daemon = EvolutionDaemon()
    return _daemon


if __name__ == "__main__":
    import signal
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    daemon = EvolutionDaemon()
    loop = asyncio.new_event_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, loop.stop)
        loop.add_signal_handler(signal.SIGINT, loop.stop)
    except (NotImplementedError, RuntimeError):
        pass
    try:
        loop.run_until_complete(daemon.run())
    except KeyboardInterrupt:
        logger.info("Daemon stopped by user")
    finally:
        loop.close()
