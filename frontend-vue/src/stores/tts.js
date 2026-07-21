import { defineStore } from "pinia"
import { ref } from "vue"

export const useTtsStore = defineStore("tts", () => {
  const engine = ref(localStorage.getItem("tts_engine") || "edge")
  const voice = ref(localStorage.getItem("tts_voice") || "zh-CN-XiaoxiaoNeural")
  const speed = ref(parseFloat(localStorage.getItem("tts_speed") || "1"))
  const autoSpeak = ref(localStorage.getItem("tts_auto") !== "false")
  const isSpeaking = ref(false)
  let audioEl = null

  async function speak(text, emotion = "neutral") {
    if (!text || !autoSpeak.value) return
    stop()

    const rate = emotion === "happy" ? `+${Math.round((speed.value - 1) * 50 + 10)}%` : `${Math.round((speed.value - 1) * 50)}%`
    const pitch = emotion === "happy" ? "+15Hz" : emotion === "sad" ? "-10Hz" : "+0Hz"

    try {
      const res = await fetch("/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: voice.value, rate, pitch }),
      })
      if (!res.ok) throw new Error("TTS failed")

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      audioEl = new Audio(url)
      isSpeaking.value = true
      audioEl.onended = () => { isSpeaking.value = false }
      await audioEl.play()
    } catch (e) {
      console.error("TTS error:", e)
      isSpeaking.value = false
    }
  }

  function stop() {
    if (audioEl) {
      audioEl.pause()
      audioEl = null
    }
    isSpeaking.value = false
  }

  function setEngine(e) { engine.value = e; localStorage.setItem("tts_engine", e) }
  function setVoice(v) { voice.value = v; localStorage.setItem("tts_voice", v) }
  function setSpeed(s) { speed.value = s; localStorage.setItem("tts_speed", String(s)) }
  function setAutoSpeak(a) { autoSpeak.value = a; localStorage.setItem("tts_auto", String(a)) }

  return { engine, voice, speed, autoSpeak, isSpeaking, speak, stop, setEngine, setVoice, setSpeed, setAutoSpeak }
})
