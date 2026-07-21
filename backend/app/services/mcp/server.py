"""
MCP (Model Context Protocol) 服务
==================================
让 Lord-King 支持标准 MCP 协议,可以:
1. 作为 MCP Server 对外暴露工具
2. 连接外部 MCP Server 扩展能力
3. 与 Claude Desktop / Cursor / VS Code 等客户端集成
"""

import json
import os
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from loguru import logger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import asyncio


class MCPServer:
    """
    MCP 协议服务器
    实现 MCP JSON-RPC 2.0 协议,暴露 Lord-King 的工具
    """

    def __init__(self, skills_engine=None, tool_registry=None):
        self.skills_engine = skills_engine
        self.tool_registry = tool_registry  # 兼容旧版 TOOL_REGISTRY
        self.server_info = {
            "name": "lordking-mcp",
            "version": "1.0.0",
            "description": "Lord-King AI Assistant MCP Server"
        }

    def get_server_info(self) -> Dict:
        return self.server_info

    def list_tools(self) -> List[Dict]:
        """列出所有可用工具 (MCP tools/list)"""
        tools = []

        # 从技能引擎获取
        if self.skills_engine:
            for definition in self.skills_engine.get_tool_definitions():
                func = definition.get("function", {})
                tools.append({
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "inputSchema": func.get("parameters", {})
                })

        # 从旧版工具注册表获取
        if self.tool_registry:
            for name, func in self.tool_registry.items():
                # 避免重复
                if not any(t["name"] == name for t in tools):
                    doc = (func.__doc__ or "").strip().split("\n")[0]
                    tools.append({
                        "name": name,
                        "description": doc or f"Tool: {name}",
                        "inputSchema": {"type": "object", "properties": {}}
                    })

        return tools

    async def call_tool(self, name: str, arguments: dict) -> Dict:
        """调用工具 (MCP tools/call)"""
        # 优先从技能引擎执行
        if self.skills_engine and name in self.skills_engine.tool_funcs:
            result = await self.skills_engine.execute_tool(name, arguments)
            return {
                "content": [{"type": "text", "text": result}],
                "isError": False
            }

        # 兼容旧版
        if self.tool_registry and name in self.tool_registry:
            try:
                func = self.tool_registry[name]
                if asyncio.iscoroutinefunction(func):
                    result = await func(**arguments)
                else:
                    result = func(**arguments)
                return {
                    "content": [{"type": "text", "text": str(result)}],
                    "isError": False
                }
            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True
                }

        return {
            "content": [{"type": "text", f"text": f"Unknown tool: {name}"}],
            "isError": True
        }

    async def handle_jsonrpc(self, request: Dict) -> Optional[Dict]:
        """处理 MCP JSON-RPC 请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": self.server_info,
                        "capabilities": {"tools": {}}
                    }
                }

            elif method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": self.list_tools()}
                }

            elif method == "tools/call":
                result = await self.call_tool(
                    params.get("name", ""),
                    params.get("arguments", {})
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result
                }

            elif method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

        except Exception as e:
            logger.error(f"MCP error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            }


def setup_mcp_routes(app: FastAPI, mcp_server: MCPServer):
    """为 FastAPI 应用添加 MCP 路由"""

    @app.post("/mcp")
    async def mcp_endpoint(request: Request):
        """MCP JSON-RPC 端点"""
        body = await request.json()
        response = await mcp_server.handle_jsonrpc(body)
        if response is None:
            return JSONResponse(status_code=204, content="")
        return JSONResponse(content=response)

    @app.get("/mcp")
    async def mcp_sse():
        """MCP SSE 端点 (流式)"""
        async def event_stream():
            # SSE 初始化
            yield f"event: message\ndata: {json.dumps({'type': 'endpoint', 'endpoint': '/mcp'})}\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/mcp/tools")
    async def mcp_list_tools():
        """列出所有 MCP 工具 (REST 接口)"""
        return {"tools": mcp_server.list_tools()}
