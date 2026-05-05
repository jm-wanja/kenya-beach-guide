import { defineStore } from 'pinia'
import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

export const useBeachStore = defineStore('beach', {
  state: () => ({
    beaches: [],
    currentBeach: null,
    activityScores: null,
    activityForecast: [],
    bestTimes: {},
    alerts: [],
    loading: false,
    error: null,
  }),

  actions: {
    async fetchBeaches() {
      this.loading = true
      try {
        const { data } = await api.get('/beaches')
        this.beaches = data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async fetchBeachDetail(code) {
      this.loading = true
      try {
        const { data } = await api.get(`/beaches/${code}`)
        this.currentBeach = data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async fetchActivityScores(code) {
      try {
        const { data } = await api.get(`/activities/${code}`)
        this.activityScores = data
      } catch (err) {
        this.error = err.message
      }
    },

    async fetchBestTimes(code, activity) {
      try {
        const { data } = await api.get(`/activities/${code}/best-times`, {
          params: { activity, top_n: 5 },
        })
        this.bestTimes[activity] = data
      } catch (err) {
        this.error = err.message
      }
    },

    async fetchActivityForecast(code, hoursAhead = 48) {
      try {
        const { data } = await api.get(`/activities/${code}/forecast`, {
          params: { hours_ahead: hoursAhead },
        })
        this.activityForecast = data
      } catch (err) {
        this.error = err.message
      }
    },

    async fetchAlerts(beachCode = null) {
      try {
        const params = beachCode ? { beach_code: beachCode } : {}
        const { data } = await api.get('/alerts', { params })
        this.alerts = data
      } catch (err) {
        this.error = err.message
      }
    },
  },
})
