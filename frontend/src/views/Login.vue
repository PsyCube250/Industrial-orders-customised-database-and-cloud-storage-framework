<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">ProdFlow</h1>
      <p class="login-subtitle">制造订单与生产管理系统</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <p v-if="error" class="login-error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  error.value = ''

  try {
    await auth.login(form.username, form.password)
    router.push('/home')
  } catch (e) {
    const detail = e.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-navy-900), var(--color-navy-700));
}

.login-card {
  width: 400px;
  padding: var(--space-12) var(--space-10);
  background: #fff;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
}

.login-title {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-navy-800);
  text-align: center;
  letter-spacing: 2px;
}

.login-subtitle {
  font-size: var(--text-sm);
  color: var(--color-gray-500);
  text-align: center;
  margin-top: var(--space-2);
  margin-bottom: var(--space-8);
}

.login-form {
  margin-top: var(--space-6);
}

.login-btn {
  width: 100%;
}

.login-error {
  color: var(--color-danger);
  font-size: var(--text-sm);
  text-align: center;
  margin-top: var(--space-2);
}
</style>
