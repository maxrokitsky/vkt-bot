import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import DashboardView from '@/views/DashboardView.vue'
import ChatsView from '@/views/ChatsView.vue'
import RolesView from '@/views/RolesView.vue'
import ChatUsersView from '@/views/ChatUsersView.vue'
import ChatUserDetailView from '@/views/ChatUserDetailView.vue'
import GitLabWebhooksView from '@/views/GitLabWebhooksView.vue'
import BotSettingsView from '@/views/BotSettingsView.vue'
import LogsView from '@/views/LogsView.vue'
import WebhooksView from '@/views/WebhooksView.vue'
import MainLayout from '@/layouts/MainLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { title: "Вход", requiresAuth: false },
    },
    {
      path: '/',
      component: MainLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: DashboardView,
          meta: { title: "Главная", requiresAuth: true },
        },
        {
          path: 'chats',
          name: 'chats',
          component: ChatsView,
          meta: { title: "Чаты", requiresAuth: true },
        },
        {
          path: 'roles',
          name: 'roles',
          component: RolesView,
          meta: { title: "Роли", requiresAuth: true },
        },
        {
          path: 'chat-users',
          name: 'chat-users',
          component: ChatUsersView,
          meta: { title: "Пользователи чатов", requiresAuth: true },
        },
        {
          path: 'chat-users/:id',
          name: 'chat-user-detail',
          component: ChatUserDetailView,
          meta: { title: "Детали пользователя", requiresAuth: true },
        },
        {
          path: 'gitlab/webhooks',
          name: 'gitlab-webhooks',
          component: GitLabWebhooksView,
          meta: { title: "GitLab Webhooks", requiresAuth: true, requiresAdmin: true },
        },
        {
          path: 'bot-settings',
          name: 'bot-settings',
          component: BotSettingsView,
          meta: { title: "Настройки бота", requiresAuth: true, requiresAdmin: true },
        },
        {
          path: 'logs',
          name: 'logs',
          component: LogsView,
          meta: { title: "Логи аудита", requiresAuth: true, requiresAdmin: true },
        },
        {
          path: 'webhooks',
          name: 'webhooks',
          component: WebhooksView,
          meta: { title: "Вебхуки", requiresAuth: true },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (to.path === '/login') {
    // A magic link always wins, even over an existing session.
    if (to.query.token) return true
    // Only skip the login page for a session the server has confirmed.
    if (await authStore.ensureUser()) return { path: '/' }
    return true
  }

  if (!to.meta.requiresAuth) return true

  if (!(await authStore.ensureUser())) {
    return {
      path: '/login',
      query: to.fullPath === '/' ? {} : { redirect: to.fullPath },
    }
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return { path: '/' }
  }

  return true
})

export default router
