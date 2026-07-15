import { defineStore } from 'pinia'
import client from '@/api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    username: (state) => state.user?.username || '',
    role: (state) => state.user?.role || '',
  },

  actions: {
    async login(username, password) {
      const formData = new FormData()
      formData.append('username', username)
      formData.append('password', password)

      const res = await client.post('/auth/login', formData)
      const { access_token } = res.data
      this.token = access_token
      localStorage.setItem('token', access_token)

      await this.fetchUser()
    },

    async fetchUser() {
      const res = await client.get('/auth/me')
      this.user = res.data
      localStorage.setItem('user', JSON.stringify(res.data))
    },

    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
