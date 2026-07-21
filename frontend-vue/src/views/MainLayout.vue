<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAffectionStore } from '../stores/affection'
import { useTtsStore } from '../stores/tts'
import ChatPanel from '../components/ChatPanel.vue'
import Live2DStage from '../components/Live2DStage.vue'
import AffectionPill from '../components/AffectionPill.vue'
import MainActionBtn from '../components/MainActionBtn.vue'

const auth = useAuthStore()
const affection = useAffectionStore()
const tts = useTtsStore()
const router = useRouter()
const showSettings = ref(false)
const showSidebar = ref(false)

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="main-layout">
    <!-- Header -->
    <header class="header glass">
      <div class="header-left">
        <button class="icon-btn" @click="showSidebar = !showSidebar">☰</button>
        <h1 class="title">🌸 Lord King</h1>
      </div>
      <div class="header-center">
        <AffectionPill />
      </div>
      <div class="header-right">
        <button class="icon-btn" @click="router.push('/skills')" title="技能">⚡</button>
        <button class="icon-btn" @click="router.push('/evolution')" title="进化">🧬</button>
        <button class="icon-btn" @click="showSettings = !showSettings" title="设置">⚙️</button>
        <button class="icon-btn" @click="logout" title="退出">🚪</button>
      </div>
    </header>

    <!-- Body -->
    <div class="body">
      <aside class="sidebar glass" v-if="showSidebar">
        <nav>
          <button @click="router.push('/'); showSidebar = false">💬 对话</button>
          <button @click="router.push('/skills'); showSidebar = false">⚡ 技能</button>
          <button @click="router.push('/evolution'); showSidebar = false">🧬 进化</button>
          <button @click="showSettings = true; showSidebar = false">⚙️ 设置</button>
        </nav>
      </aside>

      <main class="content">
        <Live2DStage class="live2d-area" />
        <ChatPanel class="chat-area" />
      </main>
    </div>

    <!-- FAB -->
    <MainActionBtn />

    <!-- Settings Drawer -->
    <div v-if="showSettings" class="overlay" @click.self="showSettings = false">
      <div class="drawer glass">
        <h2>设置</h2>
        <button class="close-btn" @click="showSettings = false">✕</button>
        <div class="settings-content">
          <div class="setting-item">
            <label>用户名</label>
            <span>{{ auth.user?.username || '未登录' }}</span>
          </div>
          <div class="setting-item">
            <label>TTS 引擎</label>
            <select :value="tts.engine" @change="tts.setEngine($event.target.value)">
              <option value="edge">Edge TTS</option>
              <option value="browser">浏览器合成</option>
            </select>
          </div>
          <div class="setting-item">
            <label>语音速度</label>
            <input type="range" min="0.5" max="2" step="0.1" :value="tts.speed" @change="tts.setSpeed(parseFloat($event.target.value))" />
            <span>{{ tts.speed }}x</span>
          </div>
          <div class="setting-item">
            <label>自动朗读</label>
            <input type="checkbox" :checked="tts.autoSpeak" @change="tts.setAutoSpeak($event.target.checked)" />
          </div>
          <button class="btn" @click="tts.testVoice()">🎤 测试语音</button>
          <button class="btn btn-danger" @click="logout()">退出登录</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: relative;
  z-index: 1;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  margin: 8px;
  border-radius: var(--radius-lg);
}
.header-left, .header-center, .header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title {
  font-size: 18px;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.icon-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  padding: 6px;
  border-radius: var(--radius-sm);
  transition: background 0.2s;
}
.icon-btn:hover { background: rgba(255,107,157,0.1); }
.body {
  flex: 1;
  display: flex;
  overflow: hidden;
  gap: 8px;
  padding: 0 8px 8px;
}
.sidebar {
  width: 200px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}
.sidebar nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sidebar button {
  text-align: left;
  padding: 10px 12px;
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  color: var(--text-primary);
}
.sidebar button:hover { background: rgba(255,107,157,0.1); }
.content {
  flex: 1;
  display: flex;
  gap: 8px;
  overflow: hidden;
}
.live2d-area {
  width: 35%;
  min-width: 250px;
}
.chat-area {
  flex: 1;
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  display: flex;
  justify-content: flex-end;
  z-index: 100;
}
.drawer {
  width: 360px;
  max-width: 90vw;
  height: 100%;
  padding: 24px;
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
  overflow-y: auto;
}
.drawer h2 { margin-bottom: 16px; }
.close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
}
.settings-content { display: flex; flex-direction: column; gap: 16px; }
.setting-item { display: flex; align-items: center; gap: 12px; }
.setting-item label { min-width: 80px; font-size: 14px; }
.setting-item select, .setting-item input[type="range"] { flex: 1; }
.btn-danger { background: linear-gradient(135deg, #ff4757, #ff6b81); }
@media (max-width: 768px) {
  .live2d-area { display: none; }
  .sidebar { position: fixed; z-index: 50; height: 100%; }
}
</style>