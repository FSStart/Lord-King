export function useTTS() {
  let audioEl = null
  let queue = []
  let busy = false

  async function speak(text, voice = "zh-CN-XiaoxiaoNeural", rate = "+0%", pitch = "+0Hz") {
    if (!text) return
    stop()

    try {
      const res = await fetch("/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice, rate, pitch }),
      })
      if (!res.ok) throw new Error("TTS failed")

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      audioEl = new Audio(url)
      await audioEl.play()
    } catch (e) {
      console.error("TTS error:", e)
    }
  }

  function stop() {
    if (audioEl) {
      audioEl.pause()
      audioEl = null
    }
  }

  return { speak, stop }
}
