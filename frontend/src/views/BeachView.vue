<template>
  <div v-if="beach">
    <router-link to="/" class="text-ocean-600 hover:text-ocean-800 mb-4 inline-block">
      ← Back to all beaches
    </router-link>

    <h1 class="text-3xl font-bold text-ocean-800 mb-2">{{ beach.beach.name }}</h1>
    <p class="text-ocean-600 mb-6">{{ beach.beach.description }}</p>

    <!-- Current Conditions -->
    <div class="bg-white rounded-xl shadow-md p-6 mb-6">
      <h2 class="text-xl font-semibold text-ocean-700 mb-4">Current Conditions</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="text-center">
          <div class="text-2xl font-bold text-ocean-600">
            {{ beach.current_conditions.wave_height_m?.toFixed(1) ?? '—' }}m
          </div>
          <div class="text-sm text-gray-500">Waves</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-ocean-600">
            {{ beach.current_conditions.wind_speed_kmh?.toFixed(0) ?? '—' }} km/h
          </div>
          <div class="text-sm text-gray-500">Wind</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-ocean-600">
            {{ beach.current_conditions.tide_level_m?.toFixed(1) ?? '—' }}m
          </div>
          <div class="text-sm text-gray-500">Tide</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-ocean-600">
            {{ beach.current_conditions.swell_height_m?.toFixed(1) ?? '—' }}m
          </div>
          <div class="text-sm text-gray-500">Swell</div>
        </div>
      </div>
    </div>

    <!-- Activity Scores -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
      <ActivityCard
        v-for="(activity, name) in beach.activities"
        :key="name"
        :name="name"
        :activity="activity"
      />
    </div>
  </div>
  <div v-else class="text-center py-12 text-gray-500">
    Loading beach data...
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useBeachStore } from '../stores/beach'
import ActivityCard from '../components/ActivityCard.vue'

const props = defineProps({ code: String })
const store = useBeachStore()
const beach = computed(() => store.currentBeach)

onMounted(() => {
  store.fetchBeachDetail(props.code)
})
</script>
