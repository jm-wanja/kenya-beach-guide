<template>
  <div class="bg-white rounded-xl shadow-md h-64 mb-6" ref="mapContainer">
    <!-- Leaflet map renders here -->
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({ beaches: { type: Array, default: () => [] } })
const mapContainer = ref(null)
const router = useRouter()
let map = null

onMounted(async () => {
  const L = await import('leaflet')
  await import('leaflet/dist/leaflet.css')
  const markerIcon = await import('leaflet/dist/images/marker-icon.png')
  const markerIcon2x = await import('leaflet/dist/images/marker-icon-2x.png')
  const markerShadow = await import('leaflet/dist/images/marker-shadow.png')

  delete L.Icon.Default.prototype._getIconUrl
  L.Icon.Default.mergeOptions({
    iconUrl: markerIcon.default,
    iconRetinaUrl: markerIcon2x.default,
    shadowUrl: markerShadow.default,
  })

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
    const marker = L.marker([b.lat, b.lon])
      .addTo(map)
      .bindPopup(`<strong>${b.name}</strong><br><a href="#" class="text-blue-600 underline" id="goto-${b.code}">View conditions →</a>`)

    marker.on('popupopen', () => {
      setTimeout(() => {
        const el = document.getElementById(`goto-${b.code}`)
        if (el) el.addEventListener('click', (e) => {
          e.preventDefault()
          router.push({ name: 'beach', params: { code: b.code } })
        })
      }, 10)
    })
  })
}
</script>
