<template>
  <div class="token-stats">
    <!-- Time Range Selector -->
    <div class="card" style="margin-bottom: 20px;">
      <div class="time-range-selector">
        <div class="quick-ranges">
          <button
            v-for="range in quickRanges"
            :key="range.label"
            class="btn"
            :class="{ 'btn-active': selectedRange === range.value && !customRange }"
            @click="selectQuickRange(range.value)"
          >
            {{ range.label }}
          </button>
        </div>
        <div class="custom-range">
          <span>Custom:</span>
          <input type="date" v-model="customStart" @change="applyCustomRange" />
          <span>to</span>
          <input type="date" v-model="customEnd" @change="applyCustomRange" />
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading token stats...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <!-- Summary Cards -->
      <div class="summary-cards fade-in">
        <div class="stat-card">
          <div class="label">Total Requests</div>
          <div class="value">{{ formatNumber(totalRequests) }}</div>
        </div>
        <div class="stat-card">
          <div class="label">Total Tokens</div>
          <div class="value" style="color: #4ade80;">{{ formatNumber(totalTokens) }}</div>
        </div>
        <div class="stat-card">
          <div class="label">Prompt</div>
          <div class="value">{{ formatNumber(totalPrompt) }}</div>
          <div class="sub">{{ promptPercentage }}%</div>
        </div>
        <div class="stat-card">
          <div class="label">Completion</div>
          <div class="value" style="color: #60a5fa;">{{ formatNumber(totalCompletion) }}</div>
          <div class="sub">{{ completionPercentage }}%</div>
        </div>
        <div class="stat-card">
          <div class="label">Cached</div>
          <div class="value" style="color: #a855f7;">{{ formatNumber(totalCached) }}</div>
          <div class="sub">{{ cacheHitRate }}% hit</div>
        </div>
        <div class="stat-card highlight">
          <div class="label">Est. Cost</div>
          <div class="value" style="color: #fbbf24;">¥{{ estimatedCost }}</div>
          <div class="sub">{{ costPeriodLabel }}</div>
        </div>
      </div>

      <!-- Charts Section -->
      <div class="charts-section fade-in" style="margin-top: 20px;">
        <div class="chart-row">
          <!-- Line Chart - Token Trend by Service -->
          <div class="card chart-card">
            <h3>Token Usage Trend by Service</h3>
            <div class="chart-container" v-if="lineChartData.labels && lineChartData.labels.length > 0">
              <Line :data="lineChartData" :options="lineChartOptions" />
            </div>
            <div class="chart-empty" v-else>
              <p>No timeline data available</p>
            </div>
          </div>

          <!-- Pie Chart - Token Usage by Model -->
          <div class="card chart-card">
            <h3>Token Usage by Model</h3>
            <div class="chart-container" v-if="pieChartData.labels && pieChartData.labels.length > 0">
              <Pie :data="pieChartData" :options="pieChartOptions" />
            </div>
            <div class="chart-empty" v-else>
              <p>No model usage data available</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Token Usage by Service -->
      <div class="card fade-in" style="margin-top: 20px;">
        <h3>Token Usage by Service</h3>
        <div class="usage-table">
          <div class="table-header">
            <div class="col-service">Service</div>
            <div class="col-reqs">Reqs</div>
            <div class="col-prompt">Prompt</div>
            <div class="col-cached">Cached</div>
            <div class="col-completion">Completion</div>
            <div class="col-total">Total</div>
            <div class="col-pct">%</div>
          </div>
          <div v-for="stat in serviceStats" :key="stat.service_name" class="table-row">
            <div class="col-service">
              <span class="service-badge" :style="{ background: getServiceColor(stat.service_name) }">
                {{ stat.service_name }}
              </span>
            </div>
            <div class="col-reqs">{{ stat.total_requests }}</div>
            <div class="col-prompt">{{ formatNumber(stat.total_prompt) }}</div>
            <div class="col-cached">{{ formatNumber(stat.cached_tokens || 0) }}</div>
            <div class="col-completion">{{ formatNumber(stat.total_completion) }}</div>
            <div class="col-total">{{ formatNumber(stat.total_tokens) }}</div>
            <div class="col-pct">{{ getServicePercentage(stat) }}%</div>
          </div>
          <div v-if="serviceStats.length === 0" class="loading">No service usage data</div>
        </div>
      </div>

      <!-- Token Usage by Model -->
      <div class="card fade-in" style="margin-top: 20px;">
        <h3>Token Usage by Model</h3>
        <div class="usage-table">
          <div class="table-header">
            <div class="col-model">Model</div>
            <div class="col-reqs">Reqs</div>
            <div class="col-prompt">Prompt</div>
            <div class="col-cached">Cached</div>
            <div class="col-completion">Completion</div>
            <div class="col-total">Total</div>
            <div class="col-cost">Cost (¥)</div>
          </div>
          <div v-for="usage in llmUsage" :key="usage.model_name" class="table-row">
            <div class="col-model"><code>{{ usage.model_name }}</code></div>
            <div class="col-reqs">{{ usage.requests }}</div>
            <div class="col-prompt">{{ formatNumber(usage.prompt_tokens) }}</div>
            <div class="col-cached">{{ formatNumber(usage.cached_tokens || 0) }}</div>
            <div class="col-completion">{{ formatNumber(usage.completion_tokens) }}</div>
            <div class="col-total">{{ formatNumber(usage.total_tokens) }}</div>
            <div class="col-cost">{{ usage.estimated_cost || 0 }}</div>
          </div>
          <div v-if="llmUsage.length === 0" class="loading">No model usage data</div>
        </div>
      </div>

      <!-- LLM Models Status -->
      <div class="card fade-in" style="margin-top: 20px;">
        <h3>LLM Models</h3>
        <div class="models-grid">
          <div v-for="model in llmModels" :key="model.id" class="model-item">
            <div class="model-name">{{ model.name }}</div>
            <div class="model-info">
              <code>{{ model.model_name }}</code>
              <span class="price-tag">¥{{ model.input_price_per_m || 7 }}/¥{{ model.output_price_per_m || 7 }}</span>
            </div>
            <div class="model-status">
              <span class="status-dot" :class="model.is_active ? 'active' : 'inactive'"></span>
              <span :class="model.is_active ? 'text-success' : 'text-muted'">
                {{ model.is_active ? 'Active' : 'Inactive' }}
              </span>
              <span class="fail-count" v-if="model.fail_count > 0">({{ model.fail_count }} fails)</span>
            </div>
          </div>
          <div v-if="llmModels.length === 0" class="loading">No models configured</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { statsApi } from '../api'
import { Line, Pie } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
)

export default {
  components: {
    Line,
    Pie
  }
  name: 'TokenStats',
  setup() {
    const loading = ref(true)
    const error = ref(null)
    const tokenStats = ref([])
    const llmModels = ref([])
    const llmUsage = ref([])
    const llmSummary = ref({})

    // Time range selection
    const selectedRange = ref(7)
    const customRange = ref(false)
    const customStart = ref('')
    const customEnd = ref('')

    const quickRanges = [
      { label: '1h', value: 1, type: 'hours' },
      { label: '6h', value: 6, type: 'hours' },
      { label: '12h', value: 12, type: 'hours' },
      { label: '24h', value: 24, type: 'hours' },
      { label: '7d', value: 7, type: 'days' },
      { label: '30d', value: 30, type: 'days' },
      { label: '90d', value: 90, type: 'days' },
    ]

    const totalRequests = computed(() => llmUsage.value.reduce((sum, u) => sum + u.requests, 0))
    const totalPrompt = computed(() => llmSummary.value.total_prompt || 0)
    const totalCompletion = computed(() => llmSummary.value.total_completion || 0)
    const totalTokens = computed(() => llmSummary.value.total_tokens || 0)

    const totalCached = computed(() => {
      return llmSummary.value.total_cached || 0
    })

    const cacheHitRate = computed(() => {
      return llmSummary.value.cache_hit_rate || 0
    })

    const estimatedCost = computed(() => {
      return llmSummary.value.estimated_cost || 0
    })

    const promptPercentage = computed(() => {
      if (!totalTokens.value) return 0
      return ((totalPrompt.value / totalTokens.value) * 100).toFixed(1)
    })

    const completionPercentage = computed(() => {
      if (!totalTokens.value) return 0
      return ((totalCompletion.value / totalTokens.value) * 100).toFixed(1)
    })

    // Aggregate token stats by service
    const serviceStats = computed(() => {
      const services = {}
      for (const stat of tokenStats.value) {
        const svc = stat.service_name || 'unknown'
        if (!services[svc]) {
          services[svc] = {
            service_name: svc,
            total_requests: 0,
            total_prompt: 0,
            total_completion: 0,
            cached_tokens: 0
          }
        }
        services[svc].total_requests += stat.total_requests || 0
        services[svc].total_prompt += stat.total_prompt || 0
        services[svc].total_completion += stat.total_completion || 0
        services[svc].cached_tokens += stat.cached_tokens || 0
      }
      // Calculate total tokens for each service
      Object.values(services).forEach(s => {
        s.total_tokens = s.total_prompt + s.total_completion
      })
      // Sort by total tokens descending
      return Object.values(services).sort((a, b) => b.total_tokens - a.total_tokens)
    })

    const periodDescription = computed(() => {
      const range = quickRanges.find(r => r.value === selectedRange.value)
      if (range) {
        return range.type === 'hours' ? `${range.value} hours` : `${range.value} days`
      }
      return 'custom period'
    })

    const dailyAverage = computed(() => {
      const range = quickRanges.find(r => r.value === selectedRange.value)
      if (!range) return totalTokens.value
      const days = range.type === 'hours' ? range.value / 24 : range.value
      return Math.round(totalTokens.value / days)
    })

    const predictedMonthlyTokens = computed(() => {
      // Assume 30 days
      const range = quickRanges.find(r => r.value === selectedRange.value)
      if (!range) return totalTokens.value
      const days = range.type === 'hours' ? range.value / 24 : range.value
      return Math.round((totalTokens.value / days) * 30)
    })

    const estimatedMonthlyCost = computed(() => {
      // Rough estimate: $1 per 1M tokens
      return (predictedMonthlyTokens.value / 1000000).toFixed(2)
    })

    const predictedCost = computed(() => {
      return (predictedMonthlyTokens.value / 1000000).toFixed(2)
    })

    const rangeLabel = computed(() => {
      if (customRange.value && customStart.value && customEnd.value) {
        return `${customStart.value} to ${customEnd.value}`
      }
      const range = quickRanges.find(r => r.value === selectedRange.value)
      if (range) {
        return range.type === 'hours' ? `Last ${range.value} hours` : `Last ${range.value} days`
      }
      return 'Custom range'
    })

    // Dynamic period label for EST cost display
    const costPeriodLabel = computed(() => {
      if (customRange.value && customStart.value && customEnd.value) {
        const start = new Date(customStart.value)
        const end = new Date(customEnd.value)
        const diffTime = Math.abs(end - start)
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
        return `${diffDays} days`
      }
      const range = quickRanges.find(r => r.value === selectedRange.value)
      if (range) {
        return range.type === 'hours' ? `${range.value}h` : `${range.value} days`
      }
      return '7 days'
    })

    const serviceColors = {
      'breaking': '#ef4444',
      'daily': '#22c55e',
      'twitter': '#3b82f6',
      'knowledge_graph': '#a855f7',
      'default': '#6b7280'
    }

    const getServiceColor = (serviceName) => {
      const key = Object.keys(serviceColors).find(k => serviceName.toLowerCase().includes(k))
      return serviceColors[key] || serviceColors.default
    }

    // Timeline data for charts
    const timelineData = ref({ dates: [], services: [], data: [] })

    const loadData = async () => {
      loading.value = true
      error.value = null
      try {
        let hours = 168 // default 7 days
        let startDate = null
        let endDate = null

        if (customRange.value && customStart.value && customEnd.value) {
          startDate = customStart.value
          endDate = customEnd.value
        } else {
          const range = quickRanges.find(r => r.value === selectedRange.value)
          if (range) {
            hours = range.type === 'hours' ? range.value : range.value * 24
          }
        }

        // Use LLM API with time range
        const llmData = await statsApi.llm(hours, startDate, endDate)

        // Get service-level stats (for usage distribution chart)
        let statsData
        if (startDate && endDate) {
          statsData = await statsApi.tokenStatsByRange(startDate, endDate)
        } else {
          statsData = await statsApi.tokenStatsByRange(null, null, hours)
        }

        tokenStats.value = statsData.stats || []
        llmModels.value = llmData.stats?.models || []
        llmUsage.value = llmData.stats?.token_usage || []
        llmSummary.value = llmData.stats?.summary || {}

        // Get timeline data for charts
        try {
          const timeline = await statsApi.tokenStatsTimeline(startDate, endDate, hours)
          timelineData.value = timeline || { dates: [], services: [], data: [] }
        } catch (e) {
          console.warn('Failed to load timeline data:', e)
          timelineData.value = { dates: [], services: [], data: [] }
        }
      } catch (e) {
        error.value = e.message || 'Failed to load token stats'
      } finally {
        loading.value = false
      }
    }

    const selectQuickRange = (value) => {
      selectedRange.value = value
      customRange.value = false
      loadData()
    }

    const applyCustomRange = () => {
      if (customStart.value && customEnd.value) {
        customRange.value = true
        loadData()
      }
    }

    const formatNumber = (num) => {
      if (!num) return '0'
      return num.toLocaleString()
    }

    const getPercentage = (stat) => {
      if (!totalTokens.value) return 0
      const tokens = stat.total_prompt + stat.total_completion
      return (tokens / totalTokens.value) * 100
    }

    const getModelPromptPercent = (usage) => {
      if (!usage.total_tokens) return 0
      return (usage.prompt_tokens / usage.total_tokens) * 100
    }

    const getModelCompletionPercent = (usage) => {
      if (!usage.total_tokens) return 0
      return (usage.completion_tokens / usage.total_tokens) * 100
    }

    const getServicePercentage = (stat) => {
      if (!totalTokens.value) return 0
      return ((stat.total_tokens / totalTokens.value) * 100).toFixed(1)
    }

    // Chart colors
    const chartColors = [
      '#22c55e', '#3b82f6', '#ef4444', '#a855f7', '#f59e0b',
      '#ec4899', '#14b8a6', '#8b5cf6', '#f97316', '#06b6d4'
    ]

    // Line chart data - Token usage trend by service
    const lineChartData = computed(() => {
      const { dates, services, data } = timelineData.value
      if (!dates || dates.length === 0) {
        return {
          labels: [],
          datasets: []
        }
      }

      const datasets = services.map((service, index) => ({
        label: service,
        data: data.map(d => d[service] || 0),
        borderColor: chartColors[index % chartColors.length],
        backgroundColor: chartColors[index % chartColors.length] + '20',
        fill: false,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 5
      }))

      return {
        labels: dates,
        datasets
      }
    })

    const lineChartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#9ca3af',
            usePointStyle: true,
            padding: 20
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: (context) => {
              return `${context.dataset.label}: ${context.parsed.y.toLocaleString()} tokens`
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: '#374151'
          },
          ticks: {
            color: '#9ca3af',
            maxTicksLimit: 10
          }
        },
        y: {
          grid: {
            color: '#374151'
          },
          ticks: {
            color: '#9ca3af',
            callback: (value) => value.toLocaleString()
          }
        }
      }
    }

    // Pie chart data - Token usage by model
    const pieChartData = computed(() => {
      const usage = llmUsage.value
      if (!usage || usage.length === 0) {
        return {
          labels: [],
          datasets: []
        }
      }

      return {
        labels: usage.map(u => u.model_name || 'Unknown'),
        datasets: [{
          data: usage.map(u => u.total_tokens || 0),
          backgroundColor: chartColors.slice(0, usage.length),
          borderWidth: 0,
          hoverOffset: 10
        }]
      }
    })

    const pieChartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: '#9ca3af',
            usePointStyle: true,
            padding: 15,
            font: {
              size: 11
            }
          }
        },
        tooltip: {
          callbacks: {
            label: (context) => {
              const value = context.parsed
              const total = context.dataset.data.reduce((a, b) => a + b, 0)
              const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0
              return `${context.label}: ${value.toLocaleString()} tokens (${percentage}%)`
            }
          }
        }
      }
    }

    onMounted(() => {
      loadData()
    })

    return {
      loading,
      error,
      tokenStats,
      llmModels,
      llmUsage,
      serviceStats,
      totalRequests,
      totalPrompt,
      totalCompletion,
      totalTokens,
      totalCached,
      cacheHitRate,
      estimatedCost,
      promptPercentage,
      completionPercentage,
      estimatedMonthlyCost,
      predictedMonthlyTokens,
      predictedCost,
      dailyAverage,
      periodDescription,
      costPeriodLabel,
      selectedRange,
      customRange,
      customStart,
      customEnd,
      quickRanges,
      rangeLabel,
      selectQuickRange,
      applyCustomRange,
      formatNumber,
      getPercentage,
      getServiceColor,
      getServicePercentage,
      getModelPromptPercent,
      getModelCompletionPercent,
      // Chart data
      lineChartData,
      lineChartOptions,
      pieChartData,
      pieChartOptions
    }
  }
}
</script>

<style scoped>
/* Charts Section */
.charts-section {
  margin-top: 20px;
}

.chart-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}

.chart-card {
  padding: 20px;
}

.chart-card h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: var(--text-primary);
}

.chart-container {
  height: 300px;
  position: relative;
}

.chart-empty {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  border-radius: 8px;
}

.time-range-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
}

.quick-ranges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-ranges .btn {
  padding: 6px 12px;
  font-size: 13px;
}

.btn-active {
  background: #22c55e !important;
}

.custom-range {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-secondary);
}

.custom-range input {
  padding: 6px 10px;
  border: 1px solid var(--border-color-dark);
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--text-primary);
}

/* Summary Cards */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

.stat-card {
  background: var(--bg-tertiary);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.stat-card.highlight {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.2), rgba(251, 191, 36, 0.1));
  border: 1px solid rgba(251, 191, 36, 0.3);
}

.stat-card .label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.stat-card .value {
  font-size: 20px;
  font-weight: 700;
}

.stat-card .sub {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* Usage Table */
.usage-table {
  display: flex;
  flex-direction: column;
}

.service-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  text-transform: uppercase;
}

.col-service {
  display: flex;
  align-items: center;
}

.col-pct {
  font-weight: 600;
  color: var(--accent);
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 0.8fr 1fr 1fr 1fr 1fr 1fr;
  gap: 12px;
  padding: 10px 12px;
  background: var(--bg-tertiary);
  border-radius: 8px 8px 0 0;
  font-weight: 600;
  font-size: 12px;
  color: var(--text-secondary);
}

.table-row {
  display: grid;
  grid-template-columns: 2fr 0.8fr 1fr 1fr 1fr 1fr 1fr;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  align-items: center;
  font-size: 13px;
}

.table-row:last-child {
  border-bottom: none;
}

.col-model code {
  font-size: 12px;
  color: var(--accent);
}

.col-cost {
  font-weight: 600;
  color: #fbbf24;
}

/* Models Grid */
.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}

.model-item {
  background: var(--bg-tertiary);
  border-radius: 8px;
  padding: 12px;
}

.model-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
}

.model-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.model-info code {
  font-size: 11px;
  color: var(--text-secondary);
}

.price-tag {
  font-size: 10px;
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

.model-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.active {
  background: #4ade80;
}

.status-dot.inactive {
  background: #6b7280;
}

.text-success {
  color: #4ade80;
}

.text-muted {
  color: var(--text-muted);
}

.fail-count {
  color: #ef4444;
  font-size: 11px;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .chart-row {
    grid-template-columns: 1fr;
  }

  .chart-container {
    height: 250px;
  }

  .time-range-selector {
    flex-wrap: wrap;
  }

  .time-btn {
    padding: 6px 12px;
    font-size: 12px;
  }

  .date-range-picker {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .date-input {
    width: 100%;
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .stat-box {
    padding: 14px;
  }

  .stat-label {
    font-size: 11px;
  }

  .stat-value {
    font-size: 20px;
  }

  .token-table {
    display: block;
    overflow-x: auto;
  }

  .token-table table {
    min-width: 600px;
  }

  .token-table th,
  .token-table td {
    padding: 10px 8px;
    font-size: 12px;
  }

  .model-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .page-title {
    font-size: 18px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .stat-box {
    padding: 12px;
  }

  .stat-value {
    font-size: 18px;
  }

  .stat-sub {
    font-size: 11px;
  }

  .token-table table {
    min-width: 500px;
  }

  .token-table th,
  .token-table td {
    padding: 8px 6px;
    font-size: 11px;
  }

  .model-card {
    padding: 14px;
  }

  .model-name {
    font-size: 14px;
  }

  .model-info {
    font-size: 12px;
  }
}
</style>
