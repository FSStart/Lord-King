<template>
  <div class="settings-panel">
    <div class="setting-group">
      <h4>🎤 语音设置</h4>
      <div class="setting-row">
        <label>唤醒词</label>
        <input :value="wakeWord" @change="$emit("update:wakeWord", $event.target.value)" placeholder="小婷" />
      </div>
      <div class="setting-row">
        <label>TTS 引擎</label>
        <select :value="ttsEngine" @change="$emit("update:ttsEngine", $event.target.value)">
          <option value="edge">Edge TTS</option>
          <option value="browser">浏览器合成</option>
        </select>
      </div>
      <div class="setting-row">
        <label>语音</label>
        <select :value="voice" @change="$emit("update:voice", $event.target.value)">
          <option value="zh-CN-XiaoxiaoNeural">晓晓 (女声)</option>
          <option value="zh-CN-YunxiNeural">云希 (男声)</option>
          <option value="zh-CN-YunjianNeural">云健 (男声)</option>
          <option value="zh-CN-XiaoyiNeural">晓伊 (女声)</option>
        </select>
      </div>
      <div class="setting-row">
        <label>语速</label>
        <input type="range" min="0.5" max="2" step="0.1" :value="speed" @input="$emit("update:speed", parseFloat($event.target.value))" />
        <span>{{ speed }}x</span>
      </div>
      <div class="setting-row">
        <label>自动朗读</label>
        <input type="checkbox" :checked="autoSpeak" @change="$emit("update:autoSpeak", $event.target.checked)" />
      </div>
      <button class="btn" @click="$emit("testVoice")">🎤 测试语音</button>
    </div>
    <div class="setting-group">
      <h4>💬 聊天</h4>
      <button class="btn btn-danger" @click="$emit("clearHistory")">清空聊天记录</button>
    </div>
    <div class="setting-group">
      <h4>👤 账户</h4>
      <button class="btn btn-danger" @click="$emit("logout")">退出登录</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  wakeWord: String,
  ttsEngine: String,
  voice: String,
  speed: Number,
  autoSpeak: Boolean
})
defineEmits(["update:wakeWord", "update:ttsEngine", "update:voice", "update:speed", "update:autoSpeak", "testVoice", "clearHistory", "logout"])
</script>

<style scoped>
.setting-group {
  margin-bottom: 24px;
}
.setting-group h4 {
  margin-bottom: 12px;
  color: var(--primary);
}
.setting-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.setting-row label {
  min-width: 80px;
  font-size: 14px;
}
.setting-row input[type="text"],
.setting-row select {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  background: rgba(255,255,255,0.5);
  color: var(--text-primary);
  outline: none;
}
.setting-row input[type="range"] { flex: 1; }
.btn-danger {
  background: linear-gradient(135deg, #ff4757, #ff6b81);
}
</style>