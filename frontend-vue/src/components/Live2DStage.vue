<template>
  <div class="live2d-stage glass">
    <canvas ref="canvasRef" class="live2d-canvas"></canvas>
    <div v-if="caption" class="speech-bubble">
      {{ caption }}
    </div>
    <div class="stage-label">🌸 小婷</div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue"
import { useLive2D } from "../composables/useLive2D"
import { useTtsStore } from "../stores/tts"

const canvasRef = ref(null)
const caption = ref("")
const tts = useTtsStore()
const { init, isLoaded, isSpeaking, startLipSync, stopLipSync } = useLive2D(canvasRef, { width: 400, height: 600 })

onMounted(() => init())

watch(() => tts.isSpeaking, (val) => {
  if (val) startLipSync()
  else stopLipSync()
})

defineExpose({ startLipSync, stopLipSync })
</script>

<style scoped>
.live2d-stage {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  overflow: hidden;
  height: 100%;
}
.live2d-canvas {
  width: 100%;
  height: 100%;
}
.speech-bubble {
  position: absolute;
  bottom: 16px;
  left: 16px;
  right: 16px;
  padding: 12px 16px;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  border-radius: var(--radius-md);
  border: 1px solid var(--glass-border);
  font-size: 13px;
  max-height: 80px;
  overflow-y: auto;
}
.stage-label {
  position: absolute;
  top: 12px;
  left: 12px;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--primary);
}
</style>