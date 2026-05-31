<template>
  <div v-if="beach">
    <!-- Beach switcher -->
    <div class="flex gap-2 overflow-x-auto pb-2 mb-6 scrollbar-hide">
      <router-link
        v-for="b in beaches"
        :key="b.code"
        :to="{ name: 'beach', params: { code: b.code } }"
        class="flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors"
        :class="b.code === props.code
          ? 'bg-ocean-600 text-white'
          : 'bg-white text-ocean-700 border border-ocean-200 hover:bg-ocean-50'"
      >
        {{ b.name }}
      </router-link>
    </div>

    <h1 class="text-3xl font-bold text-ocean-800 mb-2">{{ beach.beach.name }}</h1>
    <p class="text-ocean-600 mb-6">{{ beach.beach.description }}</p>

    <!-- Current Conditions -->
    <div class="bg-white rounded-xl shadow-md p-6 mb-6">
      <div class="flex items-baseline justify-between mb-4">
        <h2 class="text-xl font-semibold text-ocean-700">Current Conditions</h2>
        <span v-if="conditionsTime" class="text-xs text-gray-400">as of {{ conditionsTime }}</span>
      </div>
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
            {{ beach.current_conditions.tide_level_m != null ? beach.current_conditions.tide_level_m.toFixed(2) : '—' }}m
            <span v-if="beach.current_conditions.tide_trend" class="text-base">
              {{ beach.current_conditions.tide_trend === 'rising' ? '↑' : '↓' }}
            </span>
          </div>
          <div class="text-sm text-gray-500">
            Tide{{ beach.current_conditions.tide_trend ? ` (${beach.current_conditions.tide_trend})` : '' }}
          </div>
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

    <!-- Future Forecast -->
    <div class="bg-white rounded-xl shadow-md p-6 mb-6">
      <h2 class="text-xl font-semibold text-ocean-700 mb-4">Plan Ahead</h2>
      <div class="flex flex-wrap items-end gap-4 mb-4">
        <div>
          <label class="block text-sm text-gray-600 mb-1">Pick a date</label>
          <input
            type="date"
            v-model="selectedDate"
            :min="todayStr"
            :max="maxDateStr"
            class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-ocean-400 focus:outline-none"
          />
        </div>
        <div>
          <label class="block text-sm text-gray-600 mb-1">Activity</label>
          <select
            v-model="selectedActivity"
            class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-ocean-400 focus:outline-none"
          >
            <option value="surfing">Surfing</option>
            <option value="kite_surfing">Kite Surfing</option>
            <option value="swimming">Swimming</option>
            <option value="kids_and_dogs">Kids & Dogs</option>
          </select>
        </div>
        <button
          @click="fetchFutureForecast"
          :disabled="!selectedDate"
          class="bg-ocean-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-ocean-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Check conditions
        </button>
      </div>

      <div v-if="futureLoading" class="text-gray-400 text-sm">Loading forecast...</div>
      <div v-else-if="futureBestTimes.length">
        <h3 class="text-md font-medium text-ocean-600 mb-2">
          Best times for {{ selectedActivity.replace('_', ' ') }} on {{ selectedDate }}
        </h3>
        <div class="space-y-2">
          <div
            v-for="slot in futureBestTimes"
            :key="slot.time"
            class="flex items-center justify-between border rounded-lg px-4 py-3"
            :class="{
              'border-green-300 bg-green-50': slot.score >= 80,
              'border-blue-300 bg-blue-50': slot.score >= 60 && slot.score < 80,
              'border-yellow-300 bg-yellow-50': slot.score >= 40 && slot.score < 60,
              'border-red-300 bg-red-50': slot.score < 40,
            }"
          >
            <div>
              <span class="font-semibold text-gray-800">{{ formatTime(slot.time) }}</span>
              <span class="ml-2 text-sm text-gray-500">{{ slot.summary }}</span>
            </div>
            <div class="text-lg font-bold" :class="scoreColor(slot.score)">
              {{ slot.score }}
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="futureSearched" class="text-gray-400 text-sm">
        No forecast data available for this date yet. Data covers up to 7 days ahead.
      </div>
    </div>
  </div>
  <div v-else class="text-center py-12 text-gray-500">
    Loading beach data...
  </div>
</template>

<script setup>
import { onMounted, computed, ref, watch } from 'vue'
import { useBeachStore } from '../stores/beach'
import ActivityCard from '../components/ActivityCard.vue'

const props = defineProps({ code: String })
const store = useBeachStore()
const beach = computed(() => store.currentBeach)
const beaches = computed(() => store.beaches)

const conditionsTime = computed(() => {
  if (!beach.value?.current_conditions) return null
  const ts = beach.value.current_conditions.weather_time || beach.value.current_conditions.tide_time
  if (!ts) return null
  const d = new Date(ts)
  const diffMs = Date.now() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Updated just now'
  if (diffMin < 60) return `Updated ${diffMin} minute${diffMin === 1 ? '' : 's'} ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `Updated ${diffHr} hour${diffHr === 1 ? '' : 's'} ago`
  const date = d.toLocaleDateString([], { day: 'numeric', month: 'short' })
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return `Updated ${date}, ${time}`
})

// Future forecast state
const selectedDate = ref('')
const selectedActivity = ref('swimming')
const futureBestTimes = ref([])
const futureLoading = ref(false)
const futureSearched = ref(false)

const todayStr = computed(() => new Date().toISOString().slice(0, 10))
const maxDateStr = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + 8)
  return d.toISOString().slice(0, 10)
})

async function fetchFutureForecast() {
  if (!selectedDate.value) return
  futureLoading.value = true
  futureSearched.value = false
  try {
    futureBestTimes.value = await store.fetchBestTimes(
      props.code,
      selectedActivity.value,
      selectedDate.value
    )
  } finally {
    futureLoading.value = false
    futureSearched.value = true
  }
}

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function scoreColor(score) {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-blue-600'
  if (score >= 40) return 'text-yellow-600'
  return 'text-red-600'
}

onMounted(() => {
  store.fetchBeachDetail(props.code)
  if (!beaches.value.length) store.fetchBeaches()
})

watch(() => props.code, (newCode) => {
  store.fetchBeachDetail(newCode)
  futureBestTimes.value = []
  futureSearched.value = false
  selectedDate.value = ''
})
</script>
