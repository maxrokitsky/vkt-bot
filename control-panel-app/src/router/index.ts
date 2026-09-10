import { createRouter, createWebHistory } from 'vue-router'
import {
  GitBranch,
  Gauge,
  MessagesSquare,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
  Webhook,
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import DashboardView from '@/views/DashboardView.vue'
import ChatsView from '@/views/ChatsView.vue'
import ChatDetailView from '@/views/ChatDetailView.vue'
import RolesView from '@/views/RolesView.vue'
import RoleDetailView from '@/views/RoleDetailView.vue'
import ChatUsersView from '@/views/ChatUsersView.vue'
import ChatUserDetailView from '@/views/ChatUserDetailView.vue'
import GitLabWebhooksView from '@/views/GitLabWebhooksView.vue'
import BotSettingsView from '@/views/BotSettingsView.vue'
import EventsView from '@/views/EventsView.vue'
import WebhooksView from '@/views/WebhooksView.vue'
import MainLayout from '@/layouts/MainLayout.vue'
// Расширение RouteMeta живёт здесь же, где описаны группы меню.
import './nav'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { title: 'Вход', requiresAuth: false },
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
          meta: {
            title: 'Обзор',
            description: 'Что сейчас у бота',
            width: 'wide',
            requiresAuth: true,
            nav: { group: 'overview', order: 1, icon: Gauge },
          },
        },
        {
          path: 'chats',
          name: 'chats',
          component: ChatsView,
          meta: {
            title: 'Чаты',
            description: 'Чаты, в которых состоит бот',
            width: 'wide',
            requiresAuth: true,
            nav: { group: 'people', order: 1, icon: MessagesSquare },
          },
        },
        {
          path: 'chats/:id',
          name: 'chat-detail',
          component: ChatDetailView,
          meta: {
            title: 'Чат',
            width: 'wide',
            requiresAuth: true,
            parent: 'chats',
          },
        },
        {
          path: 'chat-users',
          name: 'chat-users',
          component: ChatUsersView,
          meta: {
            title: 'Участники',
            description: 'Кто есть в чатах бота и какие у них роли',
            width: 'wide',
            requiresAuth: true,
            nav: { group: 'people', order: 2, icon: Users, keywords: ['пользователи'] },
          },
        },
        {
          path: 'chat-users/:id',
          name: 'chat-user-detail',
          component: ChatUserDetailView,
          meta: {
            title: 'Участник',
            width: 'medium',
            requiresAuth: true,
            parent: 'chat-users',
          },
        },
        {
          path: 'roles',
          name: 'roles',
          component: RolesView,
          meta: {
            title: 'Роли',
            description: 'Роли для призыва в чатах — #роль упоминает всех участников',
            width: 'wide',
            requiresAuth: true,
            nav: { group: 'people', order: 3, icon: ShieldCheck },
          },
        },
        {
          path: 'roles/:id',
          name: 'role-detail',
          component: RoleDetailView,
          meta: {
            title: 'Роль',
            width: 'medium',
            requiresAuth: true,
            parent: 'roles',
          },
        },
        {
          path: 'webhooks',
          name: 'webhooks',
          component: WebhooksView,
          meta: {
            title: 'Вебхуки',
            description: 'Приём запросов из внешних систем с пересылкой в чат',
            width: 'wide',
            requiresAuth: true,
            nav: { group: 'integrations', order: 1, icon: Webhook },
          },
        },
        {
          path: 'integrations/gitlab',
          name: 'gitlab-webhooks',
          component: GitLabWebhooksView,
          meta: {
            title: 'GitLab',
            description: 'Уведомления о пайплайнах GitLab в чатах',
            width: 'wide',
            requiresAuth: true,
            requiresAdmin: true,
            nav: { group: 'integrations', order: 2, icon: GitBranch, keywords: ['пайплайны'] },
          },
        },
        {
          path: 'settings',
          name: 'settings',
          component: BotSettingsView,
          meta: {
            title: 'Настройки',
            description: 'Поведение бота во всех чатах',
            width: 'narrow',
            requiresAuth: true,
            requiresAdmin: true,
            nav: { group: 'admin', order: 1, icon: Settings },
          },
        },
        {
          path: 'events',
          name: 'events',
          component: EventsView,
          meta: {
            title: 'События',
            description: 'Что делают люди, бот и внешние системы',
            width: 'wide',
            requiresAuth: true,
            nav: {
              group: 'admin',
              order: 2,
              icon: ScrollText,
              keywords: ['аудит', 'логи', 'журнал'],
            },
          },
        },
        // Старые адреса — на случай сохранённых ссылок.
        { path: 'logs', redirect: { name: 'events' } },
        { path: 'bot-settings', redirect: { name: 'settings' } },
        { path: 'gitlab/webhooks', redirect: { name: 'gitlab-webhooks' } },
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
