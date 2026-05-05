<template>
  <div class="min-h-screen bg-ocean-50">
    <nav class="bg-ocean-700 text-white shadow-lg">
      <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <router-link to="/" class="text-2xl font-bold tracking-tight">
          🏖️ Kenya Beach Guide
        </router-link>
        <div class="text-sm text-ocean-200">
          Best times for beach activities on the Kenyan coast
        </div>
      </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-6">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>
