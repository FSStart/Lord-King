<template>
  <div class="evolution-panel">
    <div class="panel-header">
      <h3>🧬 进化日志</h3>
    </div>
    <div class="event-log">
      <div v-for="(event, i) in events" :key="i" class="log-item">
        <span class="log-time">{{ event.time }}</span>
        <span class="log-text">{{ event.text }}</span>
      </div>
      <div v-if="!events.length" class="empty">暂无进化事件</div>
    </div>
    <div class="tool-gen">
      <h4>工具生成</h4>
      <div class="gen-row">
        <input v-model="toolDesc" placeholder="描述你需要的工具..." />
        <button class="btn" @click="generate">⚡ 生成</button>
      </div>
    </div>
    <div v-if="reflection" class="reflection glass">
      <h4>🪞 自我反思结果</h4>
      <pre>{{ reflection }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { useSkillsStore } from "../stores/skills"

const skills = useSkillsStore()
const events = ref([
  { time: "2026-07-21", text: "系统初始化 - Vue 3 前端架构建立" },
  { time: "2026-07-21", text: "技能模块加载完成" }
])
const toolDesc = ref("")
const reflection = ref(null)

async function generate() {
  if (!toolDesc.value.trim()) return
  const result = await skills.generateTool({ description: toolDesc.value })
  if (result) {
    events.value.unshift({ time: new Date().toLocaleDateString(), text: "生成工具: " + toolDesc.value })
    toolDesc.value = ""
  }
}

async function doReflect() {
  reflection.value = await skills.reflect()
}
defineExpose({ doReflect })
</script>

<style scoped>
.panel-header h3 { margin-bottom: 16px; }
.event-log {
  max-height: 200px;
  overflow-y: auto;
  margin-bottom: 20px;
}
.log-item {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--glass-border);
  font-size: 13px;
}
.log-time { color: var(--text-light); white-space: nowrap; }
.empty { color: var(--text-light); text-align: center; padding: 20px; }
.tool-gen { margin-bottom: 20px; }
.tool-gen h4 { margin-bottom: 12px; }
.gen-row { display: flex; gap: 12px; }
.gen-row input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.5);
  color: var(--text-primary);
  outline: none;
}
.reflection {
  padding: 16px;
  border-radius: var(--radius-md);
}
.reflection h4 { margin-bottom: 12px; }
.reflection pre {
  font-size: 12px;
  white-space: pre-wrap;
  color: var(--text-secondary);
}
</style>