<template>
  <div>
    <h1 class="text-3xl font-bold text-ocean-800 mb-2">Kenyan Coast Beach Guide</h1>
    <p class="text-ocean-600 mb-8">
      Find the best times for surfing, kite surfing, swimming, and family beach days
      at {{ beaches.length }} beaches from Diani to Lamu.
    </p>

    <!-- Map -->
    <CoastalMap :beaches="beaches" class="mb-8" />

    <!-- Beach Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <router-link
        v-for="beach in beaches"
        :key="beach.code"
        :to="{ name: 'beach', params: { code: beach.code } }"
        class="block bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow p-6"
      >
        <h2 class="text-xl font-semibold text-ocean-700 mb-2">{{ beach.name }}</h2>
        <p class="text-sm text-gray-600 mb-3">{{ beach.description }}</p>
        <div class="flex gap-2">
          <span class="text-xs bg-ocean-100 text-ocean-700 px-2 py-1 rounded">
            🏄 Surfing
          </span>
          <span class="text-xs bg-ocean-100 text-ocean-700 px-2 py-1 rounded">
            🪁 Kite
          </span>
          <span class="text-xs bg-ocean-100 text-ocean-700 px-2 py-1 rounded">
            🏊 Swim
          </span>
          <span class="text-xs bg-ocean-100 text-ocean-700 px-2 py-1 rounded">
            👶 Kids
          </span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useBeachStore } from '../stores/beach'
import CoastalMap from '../components/CoastalMap.vue'

const store = useBeachStore()
const beaches = computed(() => store.beaches)

onMounted(() => {
  store.fetchBeaches()
})
</script>
