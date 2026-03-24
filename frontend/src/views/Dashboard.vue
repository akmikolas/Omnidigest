<template>
  <div class="dashboard">
    <div v-if="loading" class="loading">Loading dashboard data...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <!-- Overview Stats - First attention layer (5 cards) -->
      <div class="grid grid-5 fade-in">
        <div class="stat-card highlight">
          <div class="stat-icon">📰</div>
          <div class="stat-content">
            <div class="label">Total Articles</div>
            <div class="value">{{ overview.articles?.total || 0 }}</div>
            <div class="sub">{{ overview.articles?.last_24h || 0 }} in last 24h</div>
          </div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-icon">🚨</div>
          <div class="stat-content">
            <div class="label">Breaking Events</div>
            <div class="value">{{ overview.breaking_news?.total_events || 0 }}</div>
            <div class="sub">{{ overview.breaking_news?.pushed || 0 }} pushed</div>
          </div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-icon">🐦</div>
          <div class="stat-content">
            <div class="label">Twitter Tweets</div>
            <div class="value">{{ overview.twitter?.total_tweets || 0 }}</div>
            <div class="sub">{{ overview.twitter?.high_impact || 0 }} high impact</div>
          </div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-icon">📡</div>
          <div class="stat-content">
            <div class="label">RSS Sources</div>
            <div class="value">{{ overview.rss_sources?.enabled || 0 }}</div>
            <div class="sub">{{ overview.rss_sources?.disabled || 0 }} disabled</div>
          </div>
        </div>
        <div class="stat-card highlight">
          <div class="stat-icon">💰</div>
          <div class="stat-content">
            <div class="label">Today's API Cost</div>
            <div class="value cost-text">${{ todayCost.toFixed(4) }}</div>
            <div class="sub">{{ formatNumber(todayInputTokens + todayOutputTokens) }} tokens</div>
          </div>
        </div>
      </div>

      <!-- Index Trend Chart -->
      <div class="card indices-chart-card fade-in" style="margin-top: 16px;">
        <div class="card-header">
          <h3>📈 Index Trend</h3>
          <div class="period-selector">
            <button
              v-for="p in periods"
              :key="p.value"
              class="period-btn"
              :class="{ active: selectedPeriod === p.value }"
              @click="selectPeriod(p.value)"
            >
              {{ p.label }}
            </button>
          </div>
        </div>
        <div class="chart-container">
          <div v-if="chartLoading" class="chart-loading">Loading chart data...</div>
          <div v-else-if="chartError" class="chart-error">{{ chartError }}</div>
          <Line v-else :data="chartData" :options="chartOptions" />
        </div>
      </div>

      <!-- Knowledge Graph -->
      <div class="kg-card fade-in" style="margin-top: 16px;">
        <KnowledgeGraph />
      </div>

      <!-- System Health - Smaller cards -->
      <div class="grid grid-3 fade-in" style="margin-top: 16px;">
        <div class="card system-card-small">
          <div class="card-header">
            <h3>🤖 LLM Models</h3>
            <span class="status-indicator" :class="overview.llm_models?.total_failures > 10 ? 'danger' : 'success'">
              {{ overview.llm_models?.total_failures > 10 ? 'Issues Detected' : 'Healthy' }}
            </span>
          </div>
          <div class="system-stats">
            <div class="system-stat">
              <span class="system-stat-value" style="color: #4ade80;">{{ overview.llm_models?.active || 0 }}</span>
              <span class="system-stat-label">Active</span>
            </div>
            <div class="system-stat">
              <span class="system-stat-value" :style="{ color: overview.llm_models?.total_failures > 10 ? '#ef4444' : 'var(--text-primary)' }">
                {{ overview.llm_models?.total_failures || 0 }}
              </span>
              <span class="system-stat-label">Failures</span>
            </div>
          </div>
        </div>

        <div class="card system-card-small">
          <div class="card-header">
            <h3>📊 Breaking News</h3>
            <span class="status-indicator" :class="overview.breaking_news?.active_stories > 0 ? 'warning' : 'success'">
              {{ overview.breaking_news?.active_stories > 0 ? 'Active Stories' : 'No Active' }}
            </span>
          </div>
          <div class="system-stats">
            <div class="system-stat">
              <span class="system-stat-value" style="color: #f59e0b;">{{ overview.breaking_news?.active_stories || 0 }}</span>
              <span class="system-stat-label">Active Stories</span>
            </div>
            <div class="system-stat">
              <span class="system-stat-value" style="color: #4ade80;">{{ overview.breaking_news?.pushed || 0 }}</span>
              <span class="system-stat-label">Pushed</span>
            </div>
          </div>
        </div>

        <div class="card system-card-small">
          <div class="card-header">
            <h3>🐦 Twitter Accounts</h3>
            <span class="status-indicator" :class="overview.twitter_accounts?.error > 0 ? 'warning' : 'success'">
              {{ overview.twitter_accounts?.error > 0 ? 'Has Issues' : 'Healthy' }}
            </span>
          </div>
          <div class="system-stats">
            <div class="system-stat">
              <span class="system-stat-value" style="color: #4ade80;">{{ overview.twitter_accounts?.active || 0 }}</span>
              <span class="system-stat-label">Active</span>
            </div>
            <div class="system-stat">
              <span class="system-stat-value" style="color: #f59e0b;">{{ overview.twitter_accounts?.cooling || 0 }}</span>
              <span class="system-stat-label">Cooling</span>
            </div>
            <div class="system-stat">
              <span class="system-stat-value" style="color: #ef4444;">{{ overview.twitter_accounts?.error || 0 }}</span>
              <span class="system-stat-label">Error</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent Events -->
      <div class="grid grid-2 fade-in" style="margin-top: 16px;">
        <!-- Breaking Events -->
        <div class="card events-card">
          <div class="card-header">
            <h3>🚨 Recent Breaking Events</h3>
            <span class="events-count">{{ breakingEvents.length }} events</span>
          </div>
          <div class="events-list">
            <div v-if="breakingEvents.length === 0" class="empty-events">
              <span class="empty-icon">✨</span>
              <p>No breaking events in recent 7 days</p>
            </div>
            <div v-else class="events-scroll-container">
              <div class="events-scroll">
                <div v-for="event in breakingEvents" :key="event.id" class="event-item">
                  <div class="event-header">
                    <span class="event-score" :class="getScoreClass(event.impact_score)">
                      {{ event.impact_score }}
                    </span>
                    <span class="event-category">{{ event.category }}</span>
                    <span class="badge" :class="event.pushed ? 'badge-success' : 'badge-warning'">
                      {{ event.pushed ? 'Pushed' : 'Pending' }}
                    </span>
                  </div>
                  <div class="event-title">{{ event.event_title }}</div>
                  <div class="event-time">{{ formatTime(event.created_at) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Twitter Events -->
        <div class="card events-card">
          <div class="card-header">
            <h3>🐦 Recent Twitter Events</h3>
            <span class="events-count">{{ twitterEvents.length }} events</span>
          </div>
          <div class="events-list">
            <div v-if="twitterEvents.length === 0" class="empty-events">
              <span class="empty-icon">✨</span>
              <p>No Twitter events in recent 7 days</p>
            </div>
            <div v-else class="events-scroll-container">
              <div class="events-scroll">
                <div v-for="event in twitterEvents" :key="event.id" class="event-item">
                  <div class="event-header">
                    <span class="event-category">{{ event.category }}</span>
                    <span class="event-sources">{{ event.source_count }} sources</span>
                    <span class="badge" :class="event.pushed ? 'badge-success' : 'badge-warning'">
                      {{ event.pushed ? 'Pushed' : 'Pending' }}
                    </span>
                  </div>
                  <div class="event-title">{{ event.event_title }}</div>
                  <div class="event-time">{{ formatTime(event.created_at) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { statsApi, astockApi } from '../api'
import KnowledgeGraph from './KnowledgeGraph.vue'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

export default {
  name: 'Dashboard',
  components: { KnowledgeGraph, Line },
  setup() {
    const loading = ref(true)
    const error = ref(null)
    const overview = ref({})
    const breakingEvents = ref([])
    const twitterEvents = ref([])

    // Today's API cost
    const todayCost = ref(0)
    const todayInputTokens = ref(0)
    const todayOutputTokens = ref(0)
    const todayCachedTokens = ref(0)

    const loadData = async () => {
      loading.value = true
      error.value = null
      try {
        const [overviewData, breakingData, twitterData, tokenData] = await Promise.all([
          statsApi.overview(),
          statsApi.breaking(7),
          statsApi.twitter(7),
          statsApi.tokenStatsByRange(null, null, 24)
        ])

        const normalizeCounts = (obj) => {
          if (!obj) return {}
          const result = {}
          for (const key in obj) {
            result[key] = obj[key] ?? 0
          }
          return result
        }

        overview.value = {
          ...overviewData,
          articles: normalizeCounts(overviewData.articles),
          breaking_news: normalizeCounts(overviewData.breaking_news),
          twitter: normalizeCounts(overviewData.twitter),
          rss_sources: normalizeCounts(overviewData.rss_sources),
          llm_models: normalizeCounts(overviewData.llm_models)
        }
        console.log('Dashboard data loaded:', overview.value)
        breakingEvents.value = breakingData.stats?.recent_events || []
        twitterEvents.value = twitterData.stats?.recent_events || []

        // Process today's token cost
        if (tokenData && tokenData.stats) {
          const stats = tokenData.stats
          // Calculate total cost from stats
          let totalCost = 0
          let totalInput = 0
          let totalOutput = 0
          let totalCached = 0

          for (const item of stats) {
            const prompt = parseInt(item.total_prompt) || 0
            const completion = parseInt(item.total_completion) || 0
            const cached = parseInt(item.cached_tokens) || 0

            totalInput += prompt
            totalOutput += completion
            totalCached += cached

            // Estimate cost: ~$1 per 1M tokens (simplified)
            const totalTokens = prompt + completion
            totalCost += totalTokens / 1000000
          }

          todayCost.value = totalCost
          todayInputTokens.value = totalInput
          todayOutputTokens.value = totalOutput
          todayCachedTokens.value = totalCached
        }
      } catch (e) {
        console.error('Dashboard API error:', e)
        error.value = e.message || 'Failed to load dashboard data'
      } finally {
        loading.value = false
      }
    }

    const getScoreClass = (score) => {
      if (score >= 80) return 'score-high'
      if (score >= 60) return 'score-medium'
      return 'score-low'
    }

    const formatTime = (time) => {
      if (!time) return '-'
      const date = new Date(time)
      return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    }

    const formatNumber = (num) => {
      if (!num) return '0'
      return num.toLocaleString()
    }

    // Chart state
    const chartLoading = ref(false)
    const chartError = ref(null)
    const selectedPeriod = ref('1d')
    const chartLabels = ref([])
    const shanghaiData = ref([])
    const shenzhenData = ref([])

    const periods = [
      { label: '1D', value: '1d' },
      { label: '1W', value: '1w' },
      { label: '1M', value: '1m' },
      { label: '3M', value: '3m' }
    ]

    const chartData = computed(() => ({
      labels: chartLabels.value,
      datasets: [
        {
          label: 'Shanghai Composite',
          data: shanghaiData.value,
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4
        },
        {
          label: 'Shenzhen Component',
          data: shenzhenData.value,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4
        }
      ]
    }))

    const chartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: 'var(--text-secondary)',
            usePointStyle: true,
            padding: 20
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#fff',
          bodyColor: '#fff',
          padding: 12,
          cornerRadius: 8
        }
      },
      scales: {
        x: {
          grid: {
            color: 'var(--border-color)',
            drawBorder: false
          },
          ticks: {
            color: 'var(--text-muted)',
            maxTicksLimit: 8
          }
        },
        y: {
          grid: {
            color: 'var(--border-color)',
            drawBorder: false
          },
          ticks: {
            color: 'var(--text-muted)'
          }
        }
      }
    }

    const loadChartData = async (period) => {
      chartLoading.value = true
      chartError.value = null
      try {
        const response = await astockApi.indicesHistory('sh000001,sz399001', period)
        console.log('Index history response:', response)
        if (response && response.dates) {
          chartLabels.value = response.dates
          shanghaiData.value = response.sh000001 || []
          shenzhenData.value = response.sz399001 || []
        }
      } catch (e) {
        chartError.value = 'Failed to load chart data'
        console.error('Chart API error:', e)
      } finally {
        chartLoading.value = false
      }
    }

    const selectPeriod = (period) => {
      selectedPeriod.value = period
      loadChartData(period)
    }

    onMounted(() => {
      loadData()
      loadChartData('1d')
    })

    return {
      loading,
      error,
      overview,
      breakingEvents,
      twitterEvents,
      // Today's cost
      todayCost,
      todayInputTokens,
      todayOutputTokens,
      todayCachedTokens,
      // Chart
      chartLoading,
      chartError,
      selectedPeriod,
      periods,
      chartData,
      chartOptions,
      selectPeriod,
      // Methods
      getScoreClass,
      formatTime,
      formatNumber
    }
  }
}
</script>

<style scoped>
/* Index Chart Card */
.indices-chart-card {
  padding: 20px;
}

.indices-chart-card .card-header {
  margin-bottom: 16px;
}

.period-selector {
  display: flex;
  gap: 4px;
}

.period-btn {
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.period-btn:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.period-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.chart-container {
  height: 300px;
  position: relative;
}

.chart-loading,
.chart-error {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-size: 14px;
}

.chart-error {
  color: #ef4444;
}

/* Overview Stats - Highlight cards */
.stat-card.highlight {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-secondary);
  border-radius: 16px;
  border: 1px solid var(--border-color);
}

.cost-text {
  color: #4ade80 !important;
}

.stat-icon {
  font-size: 32px;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  border-radius: 12px;
}

.stat-content {
  flex: 1;
}

.stat-content .label {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.stat-content .value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-content .sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* System Cards */
.system-card {
  padding: 20px;
}

.system-card-small {
  padding: 14px;
}

.system-card-small .card-header {
  margin-bottom: 10px;
}

.system-card-small .card-header h3 {
  font-size: 14px;
}

.system-card-small .system-stats {
  gap: 20px;
}

.system-card-small .system-stat-value {
  font-size: 24px;
}

.system-card-small .system-stat-label {
  font-size: 11px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
}

.status-indicator {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-indicator.success {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
}

.status-indicator.warning {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.status-indicator.danger {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.system-stats {
  display: flex;
  gap: 32px;
}

.system-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.system-stat-value {
  font-size: 32px;
  font-weight: 700;
}

.system-stat-label {
  font-size: 13px;
  color: var(--text-muted);
}

/* Events Cards */
.events-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.events-count {
  font-size: 13px;
  color: var(--text-muted);
}

.events-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

/* Custom scrollbar */
.events-list::-webkit-scrollbar {
  width: 6px;
}

.events-list::-webkit-scrollbar-track {
  background: var(--bg-tertiary);
  border-radius: 3px;
}

.events-list::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.events-list::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.empty-events {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  text-align: center;
}

.empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-events p {
  color: var(--text-muted);
  margin: 0;
}

.cost-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 20px 0;
}

.cost-value {
  font-size: 42px;
  font-weight: 700;
  color: #4ade80;
  margin-bottom: 16px;
}

.cost-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.cost-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.cost-label {
  color: var(--text-muted);
}

.cost-tokens {
  color: var(--text-primary);
  font-weight: 500;
}

/* Events Scroll Container with Auto-scroll */
.events-scroll-container {
  overflow: hidden;
  height: 400px;
  position: relative;
}

.events-scroll {
  display: flex;
  flex-direction: column;
  gap: 12px;
  animation: scroll-events 60s linear infinite;
}

.events-scroll:hover {
  animation-play-state: paused;
}

@keyframes scroll-events {
  0% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(-50%);
  }
}

.events-scroll {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.event-item {
  background: var(--bg-tertiary);
  border-radius: 10px;
  padding: 14px;
  transition: transform 0.2s;
}

.event-item:hover {
  transform: translateX(4px);
}

.event-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.event-score {
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.score-high {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.score-medium {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.score-low {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.event-category {
  font-size: 12px;
  color: var(--text-secondary);
}

.event-sources {
  font-size: 12px;
  color: var(--text-muted);
}

.event-title {
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 6px;
  line-height: 1.4;
}

.event-time {
  font-size: 12px;
  color: var(--text-muted);
}

/* Mobile responsive */
@media (max-width: 768px) {
  .stat-card.highlight {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding: 16px;
  }

  .stat-icon {
    width: 48px;
    height: 48px;
    font-size: 24px;
  }

  .stat-content .value {
    font-size: 24px;
  }

  .system-card-small {
    padding: 12px;
  }

  .system-card-small .card-header h3 {
    font-size: 13px;
  }

  .system-stats {
    gap: 16px;
  }

  .system-card-small .system-stat-value {
    font-size: 20px;
  }

  .system-card-small .system-stat-label {
    font-size: 10px;
  }

  .events-scroll-container {
    height: 300px;
  }

  .events-scroll {
    gap: 10px;
  }

  .event-item {
    padding: 12px;
  }

  .event-header {
    flex-wrap: wrap;
    gap: 6px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .status-indicator {
    font-size: 11px;
  }
}

@media (max-width: 480px) {
  .stat-card.highlight {
    padding: 14px;
  }

  .stat-icon {
    width: 40px;
    height: 40px;
    font-size: 20px;
  }

  .stat-content .label {
    font-size: 12px;
  }

  .stat-content .value {
    font-size: 20px;
  }

  .stat-content .sub {
    font-size: 11px;
  }

  .events-scroll-container {
    height: 250px;
  }

  .event-title {
    font-size: 13px;
  }

  .event-time {
    font-size: 11px;
  }

  .event-score,
  .event-category,
  .event-sources {
    font-size: 11px;
  }
}

@media (max-width: 375px) {
  .stat-card.highlight {
    padding: 12px;
  }

  .stat-icon {
    width: 36px;
    height: 36px;
    font-size: 18px;
    border-radius: 10px;
  }

  .stat-content .value {
    font-size: 18px;
  }

  .events-scroll-container {
    height: 200px;
  }
}
</style>
