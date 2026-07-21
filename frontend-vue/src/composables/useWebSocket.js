export function useWebSocket() {
  let ws = null
  let reconnectTimer = null
  let listeners = {}

  function connect(token, onMessage) {
    const proto = location.protocol === "https:" ? "wss" : "ws"
    const url = `${proto}://${location.host}/ws/${token}`

    ws = new WebSocket(url)

    ws.onopen = () => {
      console.log("WS connected")
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
      emit("open")
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
        emit(data.type, data)
      } catch (e) {
        console.error("WS parse error:", e)
      }
    }

    ws.onclose = () => {
      emit("close")
      reconnectTimer = setTimeout(() => connect(token, onMessage), 5000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function send(data) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data))
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) { ws.close(); ws = null }
  }

  function on(event, fn) {
    if (!listeners[event]) listeners[event] = []
    listeners[event].push(fn)
  }

  function emit(event, data) {
    listeners[event]?.forEach(fn => fn(data))
  }

  return { connect, send, disconnect, on }
}
