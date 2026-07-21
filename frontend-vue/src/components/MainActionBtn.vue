<template>
  <div class="fab" :class="state" @click="handleClick" @mousedown="startHold" @mouseup="endHold" @mouseleave="endHold">
    <span class="fab-icon">{{ icon }}</span>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from "vue"
import { useSpeechRecognition } from "../composables/useSpeechRecognition"
import { useChatStore } from "../stores/chat"

const chat = useChatStore()
const holdTimer = ref(null)
const isHolding = ref(false)

const { isListening, transcript, toggle, start, stop } = useSpeechRecognition({
  onWakeWord: (text) => {
    chat.sendMessage(text)
  },
  onResult: (text, interim) => {
    if (!interim && isHolding.value) {
      chat.sendMessage(text)
    }
  }
})

const state = computed(() => {
  if (chat.isProcessing) return "thinking"
  if (isListening.value) return "recording"
  return "idle"
})

const icon = computed(() => {
  if (chat.isProcessing) return "⏳"
  if (isListening.value) return "🎤"
  return "🎙️"
})

function handleClick() {
  if (isHolding.value) return
  toggle()
}

function startHold() {
  holdTimer.value = setTimeout(() => {
    isHolding.value = true
    start()
  }, 300)
}

function endHold() {
  if (holdTimer.value) { clearTimeout(holdTimer.value); holdTimer.value = null }
  isHolding.value = false
  stop()
}

onUnmounted(stop)
</script>

<style scoped>
.fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(255, 107, 157, 0.4);
  z-index: 50;
  transition: transform 0.2s;
  user-select: none;
}
.fab:hover { transform: scale(1.1); }
.fab.recording {
  background: linear-gradient(135deg, #ff4757, #ff6b81);
  animation: pulse 1s infinite;
}
.fab.thinking {
  background: linear-gradient(135deg, var(--accent), #a78bfa);
  animation: pulse 1.5s infinite;
}
.fab-icon { font-size: 24px; }
</style>