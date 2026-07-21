<script setup>
import { ref, onMounted } from 'vue'
import { useSkillsStore } from '../stores/skills'

const skills = useSkillsStore()
const reflectResult = ref(null)
const isReflecting = ref(false)
const toolInput = ref('')

async function doReflect() {
  isReflecting.value = true
  reflectResult.value = await skills.reflect()
  isReflecting.value = false
}

async function doGenerate() {
  if (!toolInput.value.trim()) return
  await skills.generateTool({ description: toolInput.value })
  toolInput.value = ''
}

onMounted(() => skills.loadSkills())
</script>

<template>
  <div class="evolution-view">
    <h2>🧬 进化面板</h2>
    <p class="desc">小婷的自我进化与工具生成系统</p>

    <section class="panel glass">
      <h3>自我反思</h3>
      <button class="btn" @click="doReflect" :disabled="isReflecting">
        {{ isReflecting ? '反思中...' : '🔍 开始反思' }}
      </button>
      <div v-if="reflectResult" class="result">
        <pre>{{ JSON.stringify(reflectResult, null, 2) }}</pre>
      </div>
    </section>

    <section class="panel glass">
      <h3>工具生成</h3>
      <div class="generate-row">
        <input v-model="toolInput" placeholder="描述你需要的工具..." />
        <button class="btn" @click="doGenerate">⚡ 生成</button>
      </div>
    </section>

    <section class="panel glass">
      <h3>进化事件</h3>
      <div class="events">
        <div class="event-item">
          <span class="time">v6.0</span>
          <span class="label">系统初始化完成</span>
        </div>
        <div class="event-item">
          <span class="time">v6.0</span>
          <span class="label">Vue 3 前端架构建立</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.evolution-view {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
  overflow-y: auto;
  height: 100%;
}
h2 { margin-bottom: 8px; }
.desc { color: var(--text-secondary); margin-bottom: 24px; }
.panel {
  padding: 20px;
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}
.panel h3 { margin-bottom: 16px; color: var(--primary); }
.result {
  margin-top: 16px;
  padding: 12px;
  background: rgba(0,0,0,0.05);
  border-radius: var(--radius-sm);
  font-size: 13px;
  overflow-x: auto;
}
.generate-row {
  display: flex;
  gap: 12px;
}
.generate-row input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.5);
  color: var(--text-primary);
  outline: none;
}
.events { display: flex; flex-direction: column; gap: 12px; }
.event-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--glass-border);
}
.event-item .time {
  background: var(--primary);
  color: white;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}
</style>