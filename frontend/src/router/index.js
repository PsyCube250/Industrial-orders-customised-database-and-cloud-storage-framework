import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/home' },
      { path: 'home', name: 'Home', component: () => import('@/views/Home.vue') },
      { path: 'orders', name: 'Orders', component: () => import('@/views/Placeholder.vue') },
      { path: 'samples', name: 'Samples', component: () => import('@/views/Placeholder.vue') },
      { path: 'procurement', name: 'Procurement', component: () => import('@/views/Placeholder.vue') },
      { path: 'preparation', name: 'Preparation', component: () => import('@/views/Placeholder.vue') },
      { path: 'production', name: 'Production', component: () => import('@/views/Placeholder.vue') },
      { path: 'packaging', name: 'Packaging', component: () => import('@/views/Placeholder.vue') },
      { path: 'messages', name: 'Messages', component: () => import('@/views/Placeholder.vue') },
      { path: 'system', name: 'System', component: () => import('@/views/Placeholder.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth !== false && !auth.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && auth.isAuthenticated) {
    next('/home')
  } else {
    next()
  }
})

export default router
