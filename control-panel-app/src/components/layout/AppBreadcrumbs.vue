<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'

const route = useRoute()
const router = useRouter()

/** Крошки строятся из `meta.parent`: у панели ровно два уровня. */
const trail = computed(() => {
  const parentName = route.meta.parent
  const parent = parentName
    ? router.getRoutes().find((candidate) => candidate.name === parentName)
    : undefined
  const items = parent
    ? [{ title: parent.meta.title ?? '', path: parent.path }]
    : []
  return { items, current: route.meta.title ?? '' }
})
</script>

<template>
  <Breadcrumb>
    <BreadcrumbList>
      <template v-for="item in trail.items" :key="item.path">
        <BreadcrumbItem>
          <BreadcrumbLink as-child>
            <RouterLink :to="item.path">{{ item.title }}</RouterLink>
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
      </template>
      <BreadcrumbItem>
        <BreadcrumbPage>{{ trail.current }}</BreadcrumbPage>
      </BreadcrumbItem>
    </BreadcrumbList>
  </Breadcrumb>
</template>
