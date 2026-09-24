<template>
  <div class="app-container">
    <header class="app-header">
      <h1 class="app-title">{{ title }}</h1>
    </header>
    <div class="app-body">
      <aside class="sidebar">
        <nav class="nav-menu">
          <router-link v-for="route in navRoutes" :key="route.path" :to="route.path" class="nav-item">
            {{ route.meta?.title }}
          </router-link>
        </nav>
      </aside>
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['HistoryView']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const title = 'Solo Project'

const navRoutes = computed(() => {
  return (router.options.routes || []).filter((r: any) => r.path !== '*')
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem 2rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.app-title {
  font-size: 1.5rem;
  font-weight: 600;
}
.app-body {
  display: flex;
  flex: 1;
}
.sidebar {
  width: 200px;
  background: white;
  border-right: 1px solid #e5e7eb;
  padding: 1rem 0;
}
.nav-menu {
  display: flex;
  flex-direction: column;
}
.nav-item {
  padding: 0.75rem 1.5rem;
  color: #374151;
  text-decoration: none;
  transition: all 0.2s;
  border-left: 3px solid transparent;
}
.nav-item:hover {
  background: #f3f4f6;
  color: #667eea;
}
.nav-item.router-link-active {
  background: #eef2ff;
  color: #667eea;
  border-left-color: #667eea;
  font-weight: 500;
}
.main-content {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
}
</style>
