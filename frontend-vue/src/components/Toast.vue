<template>
  <div class="toast" :class="type">
    <span>{{ message }}</span>
  </div>
</template>

<script setup>
defineProps({ message: String, type: { type: String, default: 'info' } })
</script>

<style scoped>
.toast {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: var(--radius-md);
  background: var(--glass-bg);
  backdrop-filter: blur(16px);
  border: 1px solid var(--glass-border);
  box-shadow: var(--glass-shadow);
  z-index: 1000;
  animation: fade-in 0.3s ease;
  font-size: 14px;
}
.toast.error { border-color: #ff4757; color: #ff4757; }
.toast.success { border-color: #2ed573; color: #2ed573; }
</style>