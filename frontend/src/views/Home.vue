<template>
  <div class="home-page">
    <div class="welcome-section">
      <div>
        <h2 class="welcome-title">欢迎回来，{{ auth.username }}</h2>
        <p class="welcome-sub">以下是系统功能模块，点击进入管理</p>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.modules }}</div>
        <div class="stat-label">功能模块</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.features }}</div>
        <div class="stat-label">子功能</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.endpoints }}</div>
        <div class="stat-label">API 端点</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">v1.0</div>
        <div class="stat-label">系统版本</div>
      </div>
    </div>

    <div class="module-grid">
      <div
        v-for="mod in modules"
        :key="mod.id"
        class="module-card"
        @click="$router.push(mod.route)"
      >
        <div class="module-icon">
          <el-icon :size="28"><component :is="mod.icon" /></el-icon>
        </div>
        <div class="module-info">
          <h3 class="module-name">{{ mod.name }}</h3>
          <div class="module-features">
            <el-tag
              v-for="feat in mod.features"
              :key="feat"
              size="small"
              class="feature-tag"
            >
              {{ feat }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { modules } from '@/data/modules'

const auth = useAuthStore()

const stats = computed(() => ({
  modules: modules.length,
  features: modules.reduce((sum, m) => sum + m.features.length, 0),
  endpoints: 72,
}))
</script>

<style scoped>
.home-page {
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.welcome-section {
  margin-bottom: var(--space-6);
}

.welcome-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--color-gray-900);
}

.welcome-sub {
  font-size: var(--text-sm);
  color: var(--color-gray-500);
  margin-top: var(--space-1);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-8);
}

.stat-card {
  background: #fff;
  border-radius: var(--radius-lg);
  padding: var(--space-5) var(--space-6);
  box-shadow: var(--shadow-sm);
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-navy-800);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--color-gray-500);
  margin-top: var(--space-1);
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}

.module-card {
  background: #fff;
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  box-shadow: var(--shadow-sm);
  display: flex;
  gap: var(--space-5);
  cursor: pointer;
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
}

.module-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.module-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-md);
  background: var(--color-navy-100);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary-500);
  flex-shrink: 0;
}

.module-info {
  flex: 1;
  min-width: 0;
}

.module-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--color-gray-900);
  margin-bottom: var(--space-3);
}

.module-features {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.feature-tag {
  font-size: var(--text-xs);
}
</style>
