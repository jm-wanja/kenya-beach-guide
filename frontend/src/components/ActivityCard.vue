<template>
  <div
    class="bg-white rounded-xl shadow-md p-6 border-l-4"
    :class="borderClass"
  >
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-lg font-semibold text-gray-800">
        {{ icon }} {{ displayName }}
      </h3>
      <div
        class="text-2xl font-bold"
        :class="scoreClass"
      >
        {{ activity.score }}
      </div>
    </div>

    <div
      class="inline-block px-3 py-1 rounded-full text-sm font-medium mb-3"
      :class="ratingClass"
    >
      {{ activity.rating }}
    </div>

    <p class="text-sm text-gray-600 mb-3">{{ activity.summary }}</p>

    <div v-if="activity.tips?.length" class="mb-2">
      <div v-for="tip in activity.tips" :key="tip" class="text-sm text-gray-500 flex items-start gap-1">
        <span class="text-ocean-500">💡</span>
        <span>{{ tip }}</span>
      </div>
    </div>

    <div v-if="activity.warnings?.length">
      <div v-for="warn in activity.warnings" :key="warn" class="text-sm text-red-600 flex items-start gap-1">
        <span>⚠️</span>
        <span>{{ warn }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: String,
  activity: Object,
})

const icons = {
  surfing: '🏄',
  kite_surfing: '🪁',
  swimming: '🏊',
  kids_and_dogs: '👶🐕',
}

const names = {
  surfing: 'Surfing',
  kite_surfing: 'Kite Surfing',
  swimming: 'Swimming',
  kids_and_dogs: 'Kids & Dogs',
}

const icon = computed(() => icons[props.name] || '🏖️')
const displayName = computed(() => names[props.name] || props.name)

const borderClass = computed(() => {
  const r = props.activity.rating
  if (r === 'excellent') return 'border-green-500'
  if (r === 'good') return 'border-blue-500'
  if (r === 'fair') return 'border-yellow-500'
  if (r === 'poor') return 'border-orange-500'
  return 'border-red-500'
})

const scoreClass = computed(() => {
  const s = props.activity.score
  if (s >= 80) return 'text-green-600'
  if (s >= 60) return 'text-blue-600'
  if (s >= 40) return 'text-yellow-600'
  if (s >= 20) return 'text-orange-600'
  return 'text-red-600'
})

const ratingClass = computed(() => {
  const r = props.activity.rating
  if (r === 'excellent') return 'bg-green-100 text-green-800'
  if (r === 'good') return 'bg-blue-100 text-blue-800'
  if (r === 'fair') return 'bg-yellow-100 text-yellow-800'
  if (r === 'poor') return 'bg-orange-100 text-orange-800'
  return 'bg-red-100 text-red-800'
})
</script>
