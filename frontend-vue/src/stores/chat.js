import { defineStore } from "pinia"
import { ref } from "vue"
import { useAuthStore } from "./auth"

export const useChatStore = defineStore("chat", () => {
  const messages = ref([])
  const isProcessing = ref(false)
  const connectionMode = ref("ws")
  const ws = ref(null)

  function connect() {
    const auth = useAuthStore()
    if (!auth.token) return

    const proto = location.protocol === "https:" ? "wss" : "ws"
    const url = `${proto}://${location.host}/ws/${auth.token}`

    try {
      ws.value = new WebSocket(url)

      ws.value.onopen = () => {
        connectionMode.value = "ws"
        console.log("WS connected")
      }

      ws.value.onmessage = (event) => {
        const data = JSON.parse(event.data)
        handleMessage(data)
      }

      ws.value.onclose = () => {
        connectionMode.value = "http"
        setTimeout(connect, 5000)
      }

      ws.value.onerror = () => {
        ws.value.close()
      }
    } catch (e) {
      connectionMode.value = "http"
    }
  }

  function handleMessage(data) {
    if (data.type === "status") {
      isProcessing.value = data.status === "thinking"
    } else if (data.type === "chunk") {
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === "assistant") {
        last.content += data.content
      } else {
        messages.value.push({ role: "assistant", content: data.content })
      }
    } else if (data.type === "done") {
      isProcessing.value = false
    } else if (data.type === "error") {
      isProcessing.value = false
    }
  }

  async function sendMessage(text, images = []) {
    messages.value.push({ role: "user", content: text, images })
    isProcessing.value = true

    if (connectionMode.value === "ws" && ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ message: text, images }))
    } else {
      // HTTP fallback
      const auth = useAuthStore()
      const res = await fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${auth.token}`,
        },
        body: JSON.stringify({ message: text, images }),
      })
      const data = await res.json()
      messages.value.push({ role: "assistant", content: data.response })
      isProcessing.value = false
    }
  }

  function clearHistory() {
    messages.value = []
    const auth = useAuthStore()
    fetch("/history", {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${auth.token}` },
    })
  }

  function disconnect() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  return { messages, isProcessing, connectionMode, connect, sendMessage, clearHistory, disconnect }
})
