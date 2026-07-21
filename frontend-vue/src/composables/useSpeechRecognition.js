export function useSpeechRecognition() {
  let recognition = null
  let wakeRecognition = null
  let isListening = false

  const wakeWords = ["小婷", "小庭", "小廷", "老大", "主人", "LordKing", "xiaoting"]

  function startWakeListening(onWake) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return null

    wakeRecognition = new SpeechRecognition()
    wakeRecognition.lang = "zh-CN"
    wakeRecognition.continuous = true
    wakeRecognition.interimResults = true
    wakeRecognition.maxAlternatives = 5

    wakeRecognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript.toLowerCase()
        for (const word of wakeWords) {
          if (transcript.includes(word.toLowerCase())) {
            const cmd = transcript.split(word).pop()?.trim()
            onWake(cmd)
            break
          }
        }
      }
    }

    wakeRecognition.onerror = (e) => {
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.warn("Wake recognition error:", e.error)
      }
    }

    wakeRecognition.onend = () => {
      if (isListening) {
        try { wakeRecognition.start() } catch (e) {}
      }
    }

    wakeRecognition.start()
    isListening = true
    return wakeRecognition
  }

  function stopWakeListening() {
    isListening = false
    if (wakeRecognition) {
      wakeRecognition.stop()
      wakeRecognition = null
    }
  }

  function startDictation(onResult) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return

    recognition = new SpeechRecognition()
    recognition.lang = "zh-CN"
    recognition.continuous = false
    recognition.interimResults = true

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map(r => r[0].transcript)
        .join("")
      onResult(transcript)
    }

    recognition.start()
  }

  return { startWakeListening, stopWakeListening, startDictation }
}
