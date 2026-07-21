<template>
  <div class="auth-panel glass">
    <div class="tabs">
      <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
      <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
    </div>
    <form @submit.prevent="submit">
      <div class="field">
        <input v-model="username" placeholder="用户名" required minlength="2" />
      </div>
      <div class="field">
        <input v-model="password" type="password" placeholder="密码" required minlength="4" />
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="btn submit-btn">
        {{ mode === "login" ? "登 录" : "注 册" }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref } from "vue"

const emit = defineEmits(["login", "register"])
const props = defineProps({ error: String })

const mode = ref("login")
const username = ref("")
const password = ref("")

function submit() {
  const data = { username: username.value, password: password.value }
  emit(mode.value, data)
}
</script>

<style scoped>
.auth-panel {
  width: 380px;
  max-width: 90vw;
  padding: 32px;
  border-radius: var(--radius-xl);
}
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}
.tabs button {
  flex: 1;
  padding: 10px;
  border: none;
  background: rgba(255,255,255,0.3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
}
.tabs button.active {
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: white;
}
.field { margin-bottom: 16px; }
.field input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.5);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}
.field input:focus { border-color: var(--primary); }
.submit-btn {
  width: 100%;
  padding: 12px;
  font-size: 16px;
}
.error {
  color: #ff4757;
  font-size: 13px;
  margin-bottom: 12px;
}
</style>