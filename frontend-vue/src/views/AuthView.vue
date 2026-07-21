<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AuthPanel from '../components/AuthPanel.vue'

const auth = useAuthStore()
const router = useRouter()
const error = ref('')

async function handleLogin({ username, password }) {
  error.value = ''
  try {
    await auth.login(username, password)
    router.push('/')
  } catch (e) {
    error.value = e.message || '登录失败'
  }
}

async function handleRegister({ username, password }) {
  error.value = ''
  try {
    await auth.register(username, password)
    await auth.login(username, password)
    router.push('/')
  } catch (e) {
    error.value = e.message || '注册失败'
  }
}
</script>

<template>
  <div class="auth-view">
    <AuthPanel
      @login="handleLogin"
      @register="handleRegister"
      :error="error"
    />
  </div>
</template>

<style scoped>
.auth-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 20px;
}
</style>