import { createRouter, createWebHistory } from "vue-router"
import ChatView from "../views/ChatView.vue"
import AuthView from "../views/AuthView.vue"
import SettingsView from "../views/SettingsView.vue"
import SkillsView from "../views/SkillsView.vue"
import EvolutionView from "../views/EvolutionView.vue"

const routes = [
  { path: "/", name: "chat", component: ChatView, meta: { requiresAuth: true } },
  { path: "/login", name: "login", component: AuthView },
  { path: "/settings", name: "settings", component: SettingsView, meta: { requiresAuth: true } },
  { path: "/skills", name: "skills", component: SkillsView, meta: { requiresAuth: true } },
  { path: "/evolution", name: "evolution", component: EvolutionView, meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("lordking_token")
  if (to.meta.requiresAuth && !token) {
    next("/login")
  } else if (to.path === "/login" && token) {
    next("/")
  } else {
    next()
  }
})

export default router
