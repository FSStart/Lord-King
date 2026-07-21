import { defineStore } from "pinia"
import { ref } from "vue"
import { useAuthStore } from "./auth"

export const useSkillsStore = defineStore("skills", () => {
  const skills = ref({})
  const evolutionReport = ref({})
  const loading = ref(false)

  async function loadSkills() {
    loading.value = true
    try {
      const auth = useAuthStore()
      const res = await fetch("/skills", {
        headers: { "Authorization": `Bearer ${auth.token}` },
      })
      if (res.ok) skills.value = await res.json()
    } catch (e) {
      console.error("Failed to load skills:", e)
    }
    loading.value = false
  }

  async function loadEvolution() {
    try {
      const auth = useAuthStore()
      const res = await fetch("/evolution", {
        headers: { "Authorization": `Bearer ${auth.token}` },
      })
      if (res.ok) evolutionReport.value = await res.json()
    } catch (e) {
      console.error("Failed to load evolution:", e)
    }
  }

  async function generateTool(description, name) {
    const auth = useAuthStore()
    const res = await fetch("/evolution/generate-tool", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${auth.token}` },
      body: JSON.stringify({ description, name }),
    })
    return await res.json()
  }

  async function reflect() {
    const auth = useAuthStore()
    const res = await fetch("/evolution/reflect", {
      method: "POST",
      headers: { "Authorization": `Bearer ${auth.token}` },
    })
    return await res.json()
  }

  return { skills, evolutionReport, loading, loadSkills, loadEvolution, generateTool, reflect }
})
