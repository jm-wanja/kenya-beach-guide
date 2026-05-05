<template>
  <div class="bg-white rounded-xl shadow-md h-64 mb-6" ref="mapContainer">
    <!-- Leaflet map renders here -->
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({ beaches: { type: Array, default: () => [] } })
const mapContainer = ref(null)
let map = null

onMounted(async () => {
  const L = await import('leaflet')
  await import('leaflet/dist/leaflet.css')

  map = L.map(mapContainer.value).setView([-3.5, 40.0], 7)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
  }).addTo(map)

  addMarkers(L)
})

watch(() => props.beaches, async () => {
  if (map) {
    const L = await import('leaflet')
    addMarkers(L)
  }
})

function addMarkers(L) {
  props.beaches.forEach((b) => {
    L.marker([b.lat, b.lon])
      .addTo(map)
      .bindPopup(`<strong>${b.name}</strong><br>${b.description || ''}`)
  })
}
</script>
