<template>
  <div class="placeholder-page">
    <el-result icon="info" title="模块开发中" :sub-title="subtitle">
      <template #extra>
        <el-button type="primary" @click="$router.push('/home')">
          返回首页
        </el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { menuItems } from '@/data/modules'

const route = useRoute()

const subtitle = computed(() => {
  const item = menuItems.find((m) => m.route === route.path)
  return item
    ? `「${item.name}」功能正在开发中，敬请期待`
    : '即将上线'
})
</script>

<style scoped>
.placeholder-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
</style>
