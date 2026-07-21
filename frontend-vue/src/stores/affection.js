import { defineStore } from "pinia"
import { ref } from "vue"
import { useAuthStore } from "./auth"

export const useAffectionStore = defineStore("affection", () => {
  const level = ref("")
  const levelEn = ref("stranger")
  const points = ref(0)
  const streak = ref(0)
  const totalMessages = ref(0)
  const showDetail = ref(false)
  const levelUpMessage = ref("")

  async function load() {
    const auth = useAuthStore()
    if (!auth.token) return
    try {
      const res = await fetch("/relationship", {
        headers: { "Authorization": `Bearer ${auth.token}` },
      })
      if (res.ok) {
        const data = await res.json()
        level.value = data.level
        levelEn.value = data.level_en
        points.value = data.affection
        streak.value = data.streak_days
        totalMessages.value = data.total_messages
      }
    } catch (e) {
      console.error("Failed to load relationship:", e)
    }
  }

  function showLevelUp(msg) {
    levelUpMessage.value = msg
    setTimeout(() => { levelUpMessage.value = "" }, 5000)
  }

  return { level, levelEn, points, streak, totalMessages, showDetail, levelUpMessage, load, showLevelUp }
})
