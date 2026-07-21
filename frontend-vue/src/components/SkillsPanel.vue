<template>
  <div class="skills-panel">
    <div class="stats-row">
      <div class="stat-card glass">
        <span class="stat-num">{{ stats.total }}</span>
        <span class="stat-label">技能总数</span>
      </div>
      <div class="stat-card glass">
        <span class="stat-num">{{ (stats.success / Math.max(stats.total, 1) * 100).toFixed(0) }}%</span>
        <span class="stat-label">成功率</span>
      </div>
      <div class="stat-card glass">
        <span class="stat-num">{{ stats.avgLatency }}ms</span>
        <span class="stat-label">平均延迟</span>
      </div>
    </div>
    <div class="skills-list">
      <div v-for="skill in skills" :key="skill.id" class="skill-row glass">
        <div class="skill-info">
          <strong>{{ skill.name }}</strong>
          <span>{{ skill.desc }}</span>
        </div>
        <div class="skill-stat">
          <div class="bar">
            <div class="bar-fill" :style="{ width: (skill.successRate * 100) + '%' }"></div>
          </div>
          <span>{{ (skill.successRate * 100).toFixed(0) }}%</span>
        </div>
      </div>
    </div>
    <button class="btn reflect-btn" @click="$emit("reflect")">🔍 触发自我反思</button>
  </div>
</template>

<script setup>
defineProps({
  skills: { type: Array, default: () => [] },
  stats: { type: Object, default: () => ({}) }
})
defineEmits(["reflect"])
</script>

<style scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.stat-card {
  padding: 16px;
  text-align: center;
  border-radius: var(--radius-md);
}
.stat-num {
  display: block;
  font-size: 24px;
  font-weight: bold;
  color: var(--primary);
}
.stat-label { font-size: 12px; color: var(--text-light); }
.skill-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  margin-bottom: 8px;
  border-radius: var(--radius-md);
}
.skill-info { display: flex; flex-direction: column; }
.skill-info span { font-size: 12px; color: var(--text-light); }
.skill-stat { display: flex; align-items: center; gap: 8px; }
.bar {
  width: 80px;
  height: 6px;
  background: rgba(0,0,0,0.1);
  border-radius: 3px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--secondary));
  border-radius: 3px;
}
.reflect-btn { margin-top: 16px; width: 100%; }
</style>