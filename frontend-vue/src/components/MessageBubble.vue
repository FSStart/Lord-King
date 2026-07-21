<template>
  <div class="message-bubble" :class="message.role">
    <div class="avatar">
      {{ message.role === "user" ? "👤" : "🌸" }}
    </div>
    <div class="bubble">
      <div class="content" v-html="renderedContent"></div>
      <div v-if="message.image" class="image-preview">
        <img :src="message.image" alt="upload" />
      </div>
      <span v-if="isStreaming" class="cursor">▊</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  message: { type: Object, required: true },
  isStreaming: { type: Boolean, default: false }
})

const renderedContent = computed(() => {
  let text = props.message.content || ""
  // Simple emotion tag rendering
  text = text.replace(/\[happy\]/g, "😊")
             .replace(/\[sad\]/g, "😢")
             .replace(/\[love\]/g, "💕")
             .replace(/\[angry\]/g, "😤")
             .replace(/\[shy\]/g, "😳")
             .replace(/\[think\]/g, "🤔")
  // Escape HTML
  text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  // Line breaks
  text = text.replace(/\n/g, "<br>")
  return text
})
</script>

<style scoped>
.message-bubble {
  display: flex;
  gap: 10px;
  animation: fade-in 0.3s ease;
  align-items: flex-start;
}
.message-bubble.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--glass-bg);
  font-size: 18px;
  flex-shrink: 0;
}
.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  word-break: break-word;
  line-height: 1.6;
  font-size: 14px;
}
.user .bubble {
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: white;
  border: none;
}
.cursor {
  display: inline-block;
  animation: typing 1s infinite;
  color: var(--primary);
  font-weight: bold;
}
.image-preview img {
  max-width: 200px;
  max-height: 200px;
  border-radius: var(--radius-sm);
  margin-top: 8px;
}
</style>