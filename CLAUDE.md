# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nexus AI ("Lord-King") is a voice-activated personal AI assistant with wake word **"LordKing"**. It runs as a Docker Compose stack with a FastAPI backend, PostgreSQL, Redis, Milvus Lite (vector DB for memory), and an Nginx-served static frontend.

## Running & Deployment

```bash
# One-command deploy (Linux/macOS server)
chmod +x start.sh && ./start.sh

# Manual Docker Compose
docker compose up -d --build

# Rebuild from scratch
docker compose down && docker compose build --no-cache && docker compose up -d
```

**Service ports:**
- Frontend: `http://<host>` (port 80, Nginx)
- Backend API: port 8000 (proxied through Nginx)
- Health check: `GET /health`
- Stats: `GET /stats`

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Purpose |
|---|---|
| `CLAUDE_API_KEY` | Anthropic API key (required for Claude mode) |
| `USE_QWEN` | `true` to switch LLM provider to Qwen |
| `QWEN_API_KEY` | DashScope API key (required when `USE_QWEN=true`) |
| `POSTGRES_PASSWORD` | PostgreSQL password |

To switch LLM provider: set `USE_QWEN=true` in `.env`, then `docker compose restart backend`.

## Architecture

```
frontend/index.html          # Single-page voice chat UI (vanilla JS)
backend/app/
  main.py                    # FastAPI app, HTTP routes, WebSocket handler
  config.py                  # Pydantic settings (reads from .env)
  services/
    llm_service.py           # LLM abstraction: Claude (Anthropic SDK) or Qwen (OpenAI-compatible)
    milvus_service.py        # Conversation memory via Milvus Lite (embedded vector DB)
Dockerfile                   # Python 3.11-slim, installs backend/requirements.txt
docker-compose.yml           # postgres + redis + backend + nginx
nginx.conf                   # Reverse-proxy /api → backend:8000, serves frontend static files
```

**Key design decisions:**
- `LLMService` selects provider at startup via `USE_QWEN` env var; Claude uses `AsyncAnthropic`, Qwen uses `AsyncOpenAI` (OpenAI-compatible endpoint). Default model is `claude-haiku-4-5`.
- `MilvusService` uses a hash-based placeholder embedding (`_text_to_vector`) instead of a real embedding model to avoid PyTorch/CUDA dependencies. Vector search is therefore semantic in structure only — replace `_text_to_vector` with a real embedding call when ready.
- Conversation memory is stored per `user_id` in Milvus after each WebSocket exchange. The `/history/{user_id}` DELETE endpoint clears it.
- Both services are singletons initialized at app startup via FastAPI `lifespan`.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Returns milvus/llm readiness status |
| GET | `/stats` | LLM call counts and provider info |
| POST | `/chat` | Single-turn HTTP chat |
| WS | `/ws/{client_id}` | Streaming chat via WebSocket |
| DELETE | `/history/{user_id}` | Clear user memory |

## Local Backend Development (without Docker)

```bash
cd backend
pip install -r requirements.txt
# Set env vars or create .env in project root
uvicorn app.main:app --reload --port 8000
```

Milvus Lite requires a writable path — set `MILVUS_DB_PATH` to a local path (e.g., `./data/milvus.db`).

## Logs & Debugging

```bash
docker compose logs -f backend     # tail backend logs
docker compose logs -f             # all services
docker compose ps                  # check container status
```
