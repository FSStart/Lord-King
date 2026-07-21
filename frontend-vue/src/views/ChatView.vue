<script setup>
import { ref, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import { useTtsStore } from '../stores/tts'
import MessageBubble from '../components/MessageBubble.vue'

const chat = useChatStore()
const tts = useTtsStore()
const inputText = ref('')
const messagesEl = ref(null)

chat.onMessage((data) => {
  if (data.type === 'chunk') {
    chat.appendToLastAssistant(data.content || data.text || '')
  } else if (data.type === 'done') {
    chat.isProcessing = false
    if (tts.autoSpeak && data.full) tts.speak(data.full)
  } else if (data.type === 'status') {
    chat.appendToLastAssistant(data.message || '')
  } else if (data.type === 'error') {
    chat.addAssistantMessage('出错了: ' + (data.message || '未知错误'))
  }
})

async function send() {
  const text = inputText.value.trim()
  if (!text || chat.isProcessing) return
  inputText.value = ''
  await chat.sendMessage(text)
  scrollToBottom()
}

async function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
}

watch(() => chat.messages.length, scrollToBottom)
watch(() => chat.messages[chat.messages.length - 1]?.content, scrollToBottom)

function handlePaste(e) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) {
        const reader = new FileReader()
        reader.onload = () => {
          chat.sendMessage('[图片]', { image: reader.result })
        }
        reader.readAsDataURL(file)
      }
    }
  }
}

function handleDrop(e) {
  e.preventDefault()
  const files = e.dataTransfer?.files
  if (!files) return
  for (const file of files) {
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = () => {
        chat.sendMessage('[图片]', { image: reader.result })
      }
      reader.readAsDataURL(file)
    }
  }
}
</script>

<template>
  <div class="chat-panel glass" @drop="handleDrop" @dragover.prevent>
    <div ref="messagesEl" class="messages">
      <MessageBubble
        v-for="(msg, i) in chat.messages"
        :key="i"
        :message="msg"
      />
      <div v-if="chat.isProcessing" class="thinking">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        <span>思考中...</span>
      </div>
    </div>
    <div class="input-area">
      <textarea
        v-model="inputText"
        @keydown="handleKeydown"
        @paste="handlePaste"
        placeholder="输入消息... (Enter发送, Shift+Enter换行)"
        rows="2"
      />
      <button class="send-btn" @click="send" :disabled="chat.isProcessing || !inputText.trim()">
        发送
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: var(--radius-lg);
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-light);
  font-size: 13px;
  padding: 8px 0;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  animation: typing 1.4s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
.input-area {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--glass-border);
}
textarea {
  flex: 1;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  background: rgba(255,255,255,0.5);
  color: var(--text-primary);
  font-family: var(--font-main);
  font-size: 14px;
  resize: none;
  outline: none;
}
textarea:focus { border-color: var(--primary); }
.send-btn {
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: white;
  cursor: pointer;
  font-size: 14px;
}
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>