"""
Self-Evolution Engine
AI writes new tools, self-reflects, auto-optimizes.
"""
import os, json, hashlib, traceback, re
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from loguru import logger


EVOLUTION_LOG = Path(os.getenv("EVOLUTION_LOG_PATH", "/root/Lord-King/data/evolution.json"))


class SelfEvolutionEngine:
    def __init__(self, llm_service=None, skills_engine=None):
        self.llm_service = llm_service
        from app.services.skills import get_skills_engine
        self.skills_engine = skills_engine or get_skills_engine()
        self.evolution_log = []
        self._load_log()

    def _load_log(self):
        if EVOLUTION_LOG.exists():
            try:
                self.evolution_log = json.loads(EVOLUTION_LOG.read_text(encoding="utf-8"))
            except Exception:
                self.evolution_log = []

    def _save_log(self):
        try:
            EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
            EVOLUTION_LOG.write_text(
                json.dumps(self.evolution_log[-100:], ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def _log_event(self, event_type, details):
        event = {"timestamp": datetime.now().isoformat(), "type": event_type, **details}
        self.evolution_log.append(event)
        self._save_log()
        logger.info(f"[Evolution] {event_type}: {details.get('summary', '')}")

    def _extract_code(self, text):
        match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        if "def " in text and "async" in text:
            return text.strip()
        return None

    def _check_code_safety(self, code):
        dangerous = ["os.system", "subprocess", "exec(", "eval(", "__import__",
                     "open('/etc", "shutil.rmtree", "os.remove", "os.unlink",
                     "socket", "import os", "import sys"]
        for p in dangerous:
            if p in code:
                return {"safe": False, "reason": f"Forbidden: {p}"}
        return {"safe": True}

    async def generate_tool(self, description, tool_name=None):
        if not self.llm_service:
            return {"success": False, "error": "LLM not available"}
        if not tool_name:
            tool_name = f"dynamic_{hashlib.md5(description.encode()).hexdigest()[:8]}"

        prompt = f"""Write an async Python tool function.

Tool name: {tool_name}
Description: {description}

Requirements:
1. Must be: async def tool_fn(**kwargs) -> str
2. Docstring describing the tool
3. Return string result
4. Good exception handling
5. Use only stdlib + httpx/aiohttp/feedparser
6. Under 50 lines

Output ONLY the Python code inside a code block. No explanations."""

        try:
            code = await self.llm_service.chat(
                message=prompt,
                system_prompt="You are a Python code expert. Output only code, no explanation.")
            code = self._extract_code(code)
            if not code:
                return {"success": False, "error": "No code extracted"}

            safety = self._check_code_safety(code)
            if not safety["safe"]:
                return {"success": False, "error": safety["reason"]}

            skill_path = Path(os.getenv("SKILLS_DIR", "/root/Lord-King/data/skills"))
            skill_path.mkdir(parents=True, exist_ok=True)
            file_path = skill_path / f"{tool_name}.py"

            full_code = f'"""\nDynamic tool: {tool_name}\nGenerated: {datetime.now().isoformat()}\n"""\n\n{code}\n\n\ndef get_skill():\n    from app.services.skills.engine import SkillDefinition\n    skill = SkillDefinition(\n        name="{tool_name}",\n        description="{description}",\n        version="1.0.0",\n        author="self-evolution",\n        tags=["dynamic", "auto-generated"],\n        tool_definition={{"type": "function", "function": {{"name": "{tool_name}", "description": "{description}", "parameters": {{"type": "object", "properties": {{}}}}}}}}\n    )\n    return skill, tool_fn\n'
            file_path.write_text(full_code, encoding="utf-8")
            self.skills_engine._load_skill_file(file_path)

            self._log_event("tool_generated", {"summary": f"Generated {tool_name}", "name": tool_name})
            return {"success": True, "name": tool_name, "file": str(file_path)}
        except Exception as e:
            logger.error(f"Tool generation failed: {e}")
            return {"success": False, "error": str(e)}

    async def reflect_and_improve(self):
        if not self.llm_service:
            return {"success": False, "error": "LLM not available"}
        stats = self.skills_engine.get_status()
        prompt = f"""Analyze these tool usage statistics and suggest improvements:

{json.dumps(stats, ensure_ascii=False, indent=2)}

Output strict JSON:
{{"issues": [...], "suggestions": [...], "new_tool_ideas": [...], "optimization": "..."}}"""

        try:
            response = await self.llm_service.chat(message=prompt,
                system_prompt="You are a system optimization expert. Output only JSON.")
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                analysis = json.loads(match.group())
                self._log_event("reflection", {"summary": "Reflection complete", "analysis": analysis})
                return {"success": True, "analysis": analysis}
            return {"success": False, "error": "Failed to parse JSON"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_evolution_report(self):
        return {
            "total_events": len(self.evolution_log),
            "recent_events": self.evolution_log[-20:],
            "skills_status": self.skills_engine.get_status()
        }


_evolution_engine = None

def get_evolution_engine(llm_service=None, skills_engine=None):
    global _evolution_engine
    if _evolution_engine is None:
        _evolution_engine = SelfEvolutionEngine(llm_service=llm_service, skills_engine=skills_engine)
    return _evolution_engine
