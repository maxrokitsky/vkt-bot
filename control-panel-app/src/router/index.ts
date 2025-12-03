import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import DashboardView from '@/views/DashboardView.vue'
import UsersView from '@/views/UsersView.vue'
import ChatsView from '@/views/ChatsView.vue'
import RolesView from '@/views/RolesView.vue'
import ChatUsersView from '@/views/ChatUsersView.vue'
import ChatUserDetailView from '@/views/ChatUserDetailView.vue'
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
          path: 'users',
          name: 'users',
          component: UsersView,
          meta: { title: "Пользователи", requiresAuth: true, requiresAdmin: true },
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
      ],
    },
  ],
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
    return
  }

  if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
    return
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next('/chats')
    return
  }

  next()
})

export default router
