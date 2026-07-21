import { defineStore } from "pinia"
import { ref, computed } from "vue"

export const useAuthStore = defineStore("auth", () => {
  const token = ref(localStorage.getItem("lordking_token") || "")
  const user = ref(JSON.parse(localStorage.getItem("lordking_user") || "{}"))

  const isAuthenticated = computed(() => !!token.value)

  async function login(username, password) {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || "Login failed")
    }
    const data = await res.json()
    token.value = data.access_token
    user.value = { id: data.user_id, username: data.username, nickname: data.nickname }
    localStorage.setItem("lordking_token", data.access_token)
    localStorage.setItem("lordking_user", JSON.stringify(user.value))
    return data
  }

  async function register(username, password, nickname) {
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, nickname }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || "Register failed")
    }
    return await res.json()
  }

  function logout() {
    token.value = ""
    user.value = {}
    localStorage.removeItem("lordking_token")
    localStorage.removeItem("lordking_user")
  }

  return { token, user, isAuthenticated, login, register, logout }
})
