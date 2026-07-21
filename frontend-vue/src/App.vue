<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from './stores/auth'
import { useAffectionStore } from './stores/affection'
import MainLayout from './views/MainLayout.vue'
import AuthView from './views/AuthView.vue'
import Toast from './components/Toast.vue'

const auth = useAuthStore()
const affection = useAffectionStore()
const showToast = ref(false)
const toastMsg = ref('')
const toastType = ref('info')
const sakuraPetals = ref([])

const isLoggedIn = computed(() => auth.isAuthenticated)

function showNotification(msg, type = 'info') {
  toastMsg.value = msg
  toastType.value = type
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3000)
}

onMounted(() => {
  auth.checkAuth()
  affection.loadRelationship()
  for (let i = 0; i < 15; i++) {
    sakuraPetals.value.push({
      id: i,
      left: Math.random() * 100,
      delay: Math.random() * 10,
      duration: 8 + Math.random() * 12,
      size: 8 + Math.random() * 12
    })
  }
})
</script>

<template>
  <div class="app-root">
    <div class="sakura-bg">
      <div
        v-for="petal in sakuraPetals"
        :key="petal.id"
        class="sakura-petal"
        :style="{
          left: petal.left + '%',
          animationDelay: petal.delay + 's, ' + (petal.delay * 0.7) + 's',
          animationDuration: petal.duration + 's, ' + (petal.duration * 0.5) + 's',
          width: petal.size + 'px',
          height: petal.size + 'px'
        }"
      />
    </div>
    <AuthView v-if="!isLoggedIn" />
    <MainLayout v-else />
    <Toast v-if="showToast" :message="toastMsg" :type="toastType" />
  </div>
</template>

<style scoped>
.app-root { position: relative; width: 100%; height: 100%; overflow: hidden; }
.sakura-bg { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
</style>