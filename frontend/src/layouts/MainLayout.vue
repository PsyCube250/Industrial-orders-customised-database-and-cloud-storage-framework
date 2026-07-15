<template>
  <div class="app-shell">
    <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
      <div class="sidebar-header">
        <span v-show="!isCollapsed" class="logo-text">ProdFlow</span>
        <span v-show="isCollapsed" class="logo-icon">PF</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :router="true"
        background-color="var(--color-navy-800)"
        text-color="rgba(255,255,255,0.65)"
        active-text-color="#fff"
        class="sidebar-menu"
      >
        <el-menu-item index="/home">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页</template>
        </el-menu-item>
        <el-menu-item
          v-for="item in menuItems"
          :key="item.route"
          :index="item.route"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.name }}</template>
        </el-menu-item>
      </el-menu>
    </aside>

    <div class="app-main">
      <header class="app-header">
        <div class="header-left">
          <el-button
            class="collapse-btn"
            :icon="Fold"
            @click="isCollapsed = !isCollapsed"
            text
          />
          <span class="header-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click">
            <span class="user-info">
              <el-icon :size="18"><UserFilled /></el-icon>
              <span class="username">{{ auth.username }}</span>
              <el-icon class="arrow"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  {{ auth.username }}
                  <span class="role-tag">{{ roleLabel }}</span>
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { menuItems } from '@/data/modules'
import { Fold, ArrowDown, SwitchButton } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isCollapsed = ref(false)

const activeMenu = computed(() => route.path)
const pageTitle = computed(() => {
  const item = menuItems.find((m) => m.route === route.path)
  return item?.name || '首页'
})

const roleLabel = computed(() => {
  const map = { admin: '管理员', supervisor: '主管', director: '总监', staff: '员工' }
  return map[auth.role] || auth.role
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
}

.app-sidebar {
  width: var(--sidebar-width);
  background: var(--color-navy-800);
  transition: width var(--transition-normal);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

.app-sidebar.collapsed {
  width: var(--sidebar-collapsed);
}

.sidebar-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.logo-text {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: #fff;
  letter-spacing: 1px;
}

.logo-icon {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: #fff;
}

.sidebar-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: var(--sidebar-width);
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.app-header {
  height: var(--header-height);
  background: #fff;
  border-bottom: 1px solid var(--color-gray-200);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: var(--z-header);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.collapse-btn {
  font-size: var(--text-lg);
  color: var(--color-gray-700);
}

.header-title {
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  color: var(--color-gray-900);
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  color: var(--color-gray-700);
  font-size: var(--text-sm);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.user-info:hover {
  background: var(--color-gray-100);
}

.username {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow {
  font-size: 12px;
  color: var(--color-gray-500);
}

.role-tag {
  color: var(--color-gray-500);
  font-size: var(--text-xs);
  margin-left: 4px;
}

.app-content {
  flex: 1;
  padding: var(--space-6);
  background: var(--color-gray-100);
  overflow-y: auto;
}
</style>
