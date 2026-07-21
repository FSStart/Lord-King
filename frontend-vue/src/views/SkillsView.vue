<script setup>
import { onMounted } from 'vue'
import { useSkillsStore } from '../stores/skills'

const skills = useSkillsStore()

onMounted(() => skills.loadSkills())
</script>

<template>
  <div class="skills-view">
    <h2>⚡ 技能面板</h2>
    <p class="desc">小婷当前掌握的技能列表</p>
    <div v-if="skills.isLoading" class="loading">加载中...</div>
    <div v-else class="skills-grid">
      <div v-for="skill in skills.skills" :key="skill.id" class="skill-card glass">
        <h3>{{ skill.name }}</h3>
        <p>{{ skill.desc }}</p>
        <div class="stats">
          <span>成功率: {{ ((skill.successRate || 0) * 100).toFixed(0) }}%</span>
          <span>延迟: {{ skill.latency || 0 }}ms</span>
        </div>
      </div>
    </div>
    <div class="stats-summary glass">
      <h3>统计</h3>
      <p>总技能数: {{ skills.stats.total }}</p>
      <p>成功率: {{ ((skills.stats.success / Math.max(skills.stats.total, 1)) * 100).toFixed(0) }}%</p>
      <p>平均延迟: {{ skills.stats.avgLatency }}ms</p>
    </div>
  </div>
</template>

<style scoped>
.skills-view {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
  overflow-y: auto;
  height: 100%;
}
h2 { margin-bottom: 8px; }
.desc { color: var(--text-secondary); margin-bottom: 24px; }
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.skill-card {
  padding: 16px;
  border-radius: var(--radius-md);
}
.skill-card h3 { margin-bottom: 8px; color: var(--primary); }
.skill-card p { color: var(--text-secondary); font-size: 13px; margin-bottom: 12px; }
.stats { display: flex; gap: 16px; font-size: 12px; color: var(--text-light); }
.stats-summary { padding: 16px; border-radius: var(--radius-md); }
.stats-summary h3 { margin-bottom: 12px; }
.loading { text-align: center; padding: 40px; color: var(--text-light); }
</style>