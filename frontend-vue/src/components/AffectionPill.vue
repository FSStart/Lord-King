<template>
  <div class="affection-pill glass" @click="showModal = !showModal">
    <span class="heart">💕</span>
    <span class="level">Lv.{{ affection.level }}</span>
    <span class="name">{{ affection.levelEn }}</span>
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal glass">
        <h3>💗 亲密度</h3>
        <p>等级: {{ affection.level }} - {{ affection.levelEn }}</p>
        <div class="points-bar">
          <div class="points-fill" :style="{ width: (affection.points / (affection.level * 100) * 100) + '%' }"></div>
        </div>
        <p>{{ affection.points }} / {{ affection.level * 100 }} EXP</p>
        <p>连续互动: {{ affection.streak }} 天</p>
        <button class="btn" @click="showModal = false">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { useAffectionStore } from "../stores/affection"

const affection = useAffectionStore()
const showModal = ref(false)
</script>

<style scoped>
.affection-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--radius-xl);
  cursor: pointer;
  transition: transform 0.2s;
  font-size: 13px;
}
.affection-pill:hover { transform: scale(1.05); }
.heart { font-size: 16px; }
.level {
  font-weight: bold;
  color: var(--primary);
}
.name { color: var(--text-secondary); }
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.modal {
  padding: 24px;
  border-radius: var(--radius-lg);
  width: 320px;
  max-width: 90vw;
}
.modal h3 { margin-bottom: 16px; }
.modal p { margin-bottom: 8px; font-size: 14px; }
.points-bar {
  height: 8px;
  background: rgba(0,0,0,0.1);
  border-radius: 4px;
  overflow: hidden;
  margin: 8px 0;
}
.points-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--secondary));
  border-radius: 4px;
  transition: width 0.3s;
}
</style>