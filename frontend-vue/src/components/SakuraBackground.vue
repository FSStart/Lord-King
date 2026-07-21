<template>
  <div class="sakura-bg">
    <div
      v-for="petal in petals"
      :key="petal.id"
      class="sakura-petal"
      :style="{
        left: petal.left + "%",
        animationDelay: petal.delay + "s, " + (petal.delay * 0.7) + "s",
        animationDuration: petal.duration + "s, " + (petal.duration * 0.5) + "s",
        width: petal.size + "px",
        height: petal.size + "px"
      }"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"

const petals = ref([])

onMounted(() => {
  for (let i = 0; i < 20; i++) {
    petals.value.push({
      id: i,
      left: Math.random() * 100,
      delay: Math.random() * 10,
      duration: 8 + Math.random() * 12,
      size: 8 + Math.random() * 14
    })
  }
})
</script>

<style scoped>
.sakura-bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}
</style>