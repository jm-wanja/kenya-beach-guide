<template>
  <div class="min-h-screen bg-ocean-50">
    <nav class="bg-ocean-700 text-white shadow-lg">
      <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <router-link to="/" class="text-2xl font-bold tracking-tight">
          🏖️ Kenya Beach Guide
        </router-link>
        <div class="text-right">
          <div class="text-sm text-ocean-200">Best times for beach activities on the Kenyan coast</div>
          <div class="text-xs text-ocean-300 mt-0.5">🕐 Kenya time: {{ kenyaTime }}</div>
        </div>
      </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-6">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const kenyaTime = ref('')

function updateKenyaTime() {
  kenyaTime.value = new Date().toLocaleTimeString('en-GB', {
    timeZone: 'Africa/Nairobi',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

let timer
onMounted(() => {
  updateKenyaTime()
  timer = setInterval(updateKenyaTime, 1000)
})
onUnmounted(() => clearInterval(timer))
</script>
