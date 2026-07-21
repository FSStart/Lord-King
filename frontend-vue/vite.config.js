import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
      "/tts": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/chat": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/skills": "http://localhost:8000",
      "/evolution": "http://localhost:8000",
      "/mcp": "http://localhost:8000",
      "/models": "http://localhost:8000",
      "/lib": "http://localhost:8000",
      "/relationship": "http://localhost:8000",
      "/reminders": "http://localhost:8000",
      "/profile": "http://localhost:8000",
      "/proactive-greeting": "http://localhost:8000",
      "/idle-chatter": "http://localhost:8000",
      "/history": "http://localhost:8000"
    }
  },
  build: {
    outDir: "../frontend-dist",
    emptyOutDir: true
  }
})
