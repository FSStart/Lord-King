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
- Frontend: `https://<host>` (port 443, Nginx, self-signed cert auto-generated at container start) — **voice wake word requires HTTPS** (browsers block mic on insecure origins); port 80 still serves text-only chat
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
desktop/                     # Electron desktop floating pet (wraps the web frontend, see below)
```

**Desktop floating pet (`desktop/`):** an Electron shell that loads the existing web frontend in **pet mode** (`http://<server>/?pet=1`) as a transparent, frameless, always-on-top window — no business logic is duplicated. `frontend/index.html` detects `?pet=1`, adds `body.pet-mode` (CSS hides all chrome except the Live2D character + a hover-in input bar), and wires drag-to-move (via `petAPI` IPC bridge from `preload.js`) + click-to-talk. `main.js` provides a tray menu (show/hide, always-on-top, click-through, open full UI, quit) and persists window position to `%APPDATA%/lordking-pet/config.json`. Server URL overridable via `LORDKING_URL` env. Run: `cd desktop && npm install && npm start`; package: `npm run dist:win`. Note: `webkitSpeechRecognition` (voice input) may be unreliable inside Electron; TTS/expression/text chat work normally.

**Key design decisions:**
- `LLMService` selects provider at startup via `USE_QWEN` env var; Claude uses `AsyncAnthropic`, Qwen uses `AsyncOpenAI` (OpenAI-compatible endpoint). Default model is `claude-haiku-4-5`. Note: the tool-calling path (`chat_with_tools`) uses the OpenAI-compatible API and therefore effectively requires the Qwen/DashScope provider.
- `MilvusService` now uses **real embeddings** (`text-embedding-v3` via the DashScope OpenAI-compatible endpoint) when `USE_QWEN` + `QWEN_API_KEY` are set, storing into collection `memories_v3` (dim `EMBED_DIM`, default 1024). Without an embedding key it falls back to a hash placeholder vector (`_hash_vector`) and collection `memories` (dim 384). `_embed()` degrades to hash on any API error so the collection dim stays consistent.
- **Vision (功能1):** when a chat request carries `images` (base64 data URLs), `chat_with_tools` builds an OpenAI-style multimodal message and routes to `QWEN_VL_MODEL` (default `qwen-vl-max-latest`), streaming the reply with tools disabled.
- **Structured profile (功能4):** `ProfileService` (Postgres table `user_profiles`, JSONB) extracts stable facts about the user from each exchange via a background LLM call (`asyncio.create_task`, non-blocking) and injects them into the system prompt every turn — distinct from Milvus, which stores retrievable conversation snippets.
- **Sentence-streaming TTS (功能3, frontend):** during a streamed reply the frontend splits completed sentences and synthesizes/plays them via a serial queue (`ttsQueue`/`pumpTTS`), cutting first-audio latency. Only active for the Edge TTS engine on voice/forced-speak rounds.
- Conversation memory is stored per `user_id` in Milvus after each WebSocket exchange. The `/history` DELETE endpoint clears it.
- All services are singletons initialized at app startup via FastAPI `lifespan` (`milvus`, `llm`, `redis`, `auth`, `affection`, `reminder`, `profile`).

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Returns milvus/llm readiness status |
| GET | `/stats` | LLM call counts and provider info |
| POST | `/chat` | Single-turn HTTP chat (accepts optional `images: [base64]`) |
| WS | `/ws/{token}` | Streaming chat via WebSocket (message payload accepts optional `images`) |
| GET | `/profile` | Structured facts Hiyori remembers about the user (功能4) |
| DELETE | `/history` | Clear current user's memory |

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
