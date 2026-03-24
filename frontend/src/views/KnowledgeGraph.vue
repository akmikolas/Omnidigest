<template>
  <div class="kg-page">
    <!-- Left Sidebar -->
    <aside class="kg-sidebar">
      <div class="sidebar-section">
        <h4>📊 概览</h4>
        <nav>
          <a
            :class="{ active: queryMode === 'overview' }"
            @click="queryMode = 'overview'"
          >
            <span class="icon">📈</span>
            <span class="text">总览</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-section">
        <h4>🔍 查询</h4>
        <nav>
          <a
            :class="{ active: queryMode === 'person' }"
            @click="switchMode('person')"
          >
            <span class="icon">👤</span>
            <span class="text">人物</span>
          </a>
          <a
            :class="{ active: queryMode === 'location' }"
            @click="switchMode('location')"
          >
            <span class="icon">📍</span>
            <span class="text">地点</span>
          </a>
          <a
            :class="{ active: queryMode === 'event' }"
            @click="switchMode('event')"
          >
            <span class="icon">📅</span>
            <span class="text">事件</span>
          </a>
          <a
            :class="{ active: queryMode === 'organization' }"
            @click="switchMode('organization')"
          >
            <span class="icon">🏢</span>
            <span class="text">组织</span>
          </a>
        </nav>
      </div>

      <div class="sidebar-section">
        <h4>🔤 内容</h4>
        <nav>
          <a
            :class="{ active: queryMode === 'keywords' }"
            @click="switchMode('keywords')"
          >
            <span class="icon">🔑</span>
            <span class="text">关键词</span>
          </a>
        </nav>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="kg-main">
      <div class="page-header">
        <h2>{{ getModeTitle() }}</h2>
        <button class="btn btn-sm" @click="loadData" :disabled="loading">
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>加载数据...</p>
      </div>

      <!-- Overview Mode -->
      <template v-else-if="queryMode === 'overview'">
        <!-- Stats Cards -->
        <div class="stats-grid fade-in">
          <div class="stat-card" v-for="type in entityTypes" :key="type.name">
            <div class="stat-icon" :style="{ background: type.color }">{{ type.icon }}</div>
            <div class="stat-info">
              <span class="stat-value">{{ formatNumber(type.count) }}</span>
              <span class="stat-label">{{ type.name }}</span>
            </div>
          </div>
        </div>

        <!-- Entity Trends -->
        <div class="card fade-in" style="margin-top: 16px;">
          <div class="card-header">
            <h3>📈 实体趋势 (最近7天)</h3>
          </div>
          <div class="trends-chart">
            <Line v-if="trendsData.labels.length" :data="trendsData" :options="trendsOptions" />
            <p v-else class="no-data">暂无趋势数据</p>
          </div>
        </div>

        <!-- Country Knowledge Graph -->
        <div class="card fade-in" style="margin-top: 16px;">
          <div class="card-header">
            <h3>🌍 国家关联图</h3>
            <div class="graph-controls">
              <button class="btn btn-sm" @click="resetZoom">重置视图</button>
            </div>
          </div>
          <div class="graph-legend">
            <div class="legend-item"><span class="legend-dot" style="background: #f97316;"></span>国家</div>
            <div class="legend-item"><span class="legend-dot" style="background: #3b82f6;"></span>人物</div>
            <div class="legend-item"><span class="legend-dot" style="background: #22c55e;"></span>事件</div>
          </div>
          <div ref="graphContainer" class="d3-graph-container">
            <svg ref="svgRef" class="d3-graph-svg"></svg>
          </div>
        </div>
      </template>

      <!-- Entity Search Mode -->
      <template v-else-if="['person', 'location', 'event', 'organization'].includes(queryMode)">
        <!-- Search Bar -->
        <div class="search-section card fade-in">
          <div class="search-bar">
            <input
              v-model="searchKeyword"
              type="text"
              :placeholder="`搜索${getTypeName(queryMode)}...`"
              class="search-input"
              @keyup.enter="searchEntities"
            />
            <button class="btn" @click="searchEntities">搜索</button>
          </div>
        </div>

        <!-- Entity Results -->
        <div class="entity-results card fade-in" style="margin-top: 16px;">
          <div class="card-header">
            <h3>{{ getTypeName(queryMode) }}列表</h3>
            <span class="result-count">共 {{ entities.length }} 个</span>
          </div>
          <div class="entity-list">
            <div
              v-for="entity in entities"
              :key="entity.uid"
              class="entity-item"
              @click="selectEntity(entity)"
            >
              <div class="entity-icon" :style="{ background: getEntityColor(entity) }">
                {{ getEntityIcon(entity) }}
              </div>
              <div class="entity-info">
                <span class="entity-name">{{ entity.name }}</span>
                <span class="entity-desc" v-if="entity.description">{{ truncate(entity.description, 80) }}</span>
              </div>
              <div class="entity-meta">
                <span v-if="entity.confidence" class="confidence-badge">
                  {{ (entity.confidence * 100).toFixed(0) }}%
                </span>
              </div>
            </div>
            <div v-if="entities.length === 0" class="no-data">
              暂无数据
            </div>
          </div>
        </div>

        <!-- Entity Detail Panel -->
        <div v-if="selectedEntity" class="entity-detail-panel card fade-in" style="margin-top: 16px;">
          <div class="card-header">
            <h3>📋 {{ selectedEntity.name }}</h3>
            <button class="btn-close" @click="selectedEntity = null">×</button>
          </div>
          <div class="detail-content">
            <div class="detail-row">
              <span class="detail-label">类型:</span>
              <span class="detail-value">{{ getEntityTypeName(selectedEntity) }}</span>
            </div>
            <div v-if="selectedEntity.description" class="detail-row">
              <span class="detail-label">描述:</span>
              <span class="detail-value">{{ selectedEntity.description }}</span>
            </div>
            <div v-if="selectedEntity.confidence" class="detail-row">
              <span class="detail-label">置信度:</span>
              <span class="detail-value">{{ (selectedEntity.confidence * 100).toFixed(1) }}%</span>
            </div>
            <div v-if="selectedEntity.aliases && selectedEntity.aliases.length" class="detail-row">
              <span class="detail-label">别名:</span>
              <span class="detail-value">{{ selectedEntity.aliases.join(', ') }}</span>
            </div>
            <div v-if="selectedEntity.sources" class="detail-row">
              <span class="detail-label">来源:</span>
              <span class="detail-value">{{ selectedEntity.sources }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- Keywords Mode -->
      <template v-else-if="queryMode === 'keywords'">
        <div class="keywords-layout">
          <div class="card fade-in keywords-cloud-card">
            <div class="card-header">
              <h3>🔤 新闻关键词</h3>
            </div>
            <div class="keywords-cloud">
              <span
                v-for="(keyword, index) in keywords"
                :key="keyword.word"
                class="keyword-tag"
                :style="getKeywordStyle(keyword, index)"
              >
                {{ keyword.word }}
              </span>
            </div>
          </div>

          <div class="card fade-in keywords-trend-card">
            <div class="card-header">
              <h3>📊 关键词趋势</h3>
            </div>
            <div class="keywords-trend">
              <Line v-if="keywordTrends.labels.length" :data="keywordTrends" :options="keywordTrendOptions" />
              <p v-else class="no-data">暂无趋势数据</p>
            </div>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick } from 'vue'
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
import * as d3 from 'd3'
import { kgApi } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

export default {
  name: 'KnowledgeGraph',
  components: { Line },
  setup() {
    const loading = ref(false)
    const queryMode = ref('overview')
    const searchKeyword = ref('')
    const entities = ref([])
    const selectedEntity = ref(null)
    const entityTypes = ref([])
    const keywords = ref([])
    const graphData = ref({ nodes: [], links: [] })

    // Refs for D3
    const graphContainer = ref(null)
    const svgRef = ref(null)
    let simulation = null

    // Trends data
    const trendsLabels = ref([])
    const trendsDatasets = ref({})

    // Keywords trend
    const keywordTrends = ref({ labels: [], datasets: [] })

    const formatNumber = (num) => {
      if (!num) return '0'
      return num.toLocaleString()
    }

    const truncate = (str, len) => {
      if (!str) return ''
      return str.length > len ? str.substring(0, len) + '...' : str
    }

    const getTypeName = (type) => {
      const names = {
        person: '人物',
        location: '地点',
        event: '事件',
        organization: '组织'
      }
      return names[type] || type
    }

    const getModeTitle = () => {
      const titles = {
        overview: '📊 知识图谱总览',
        person: '👤 人物查询',
        location: '📍 地点查询',
        event: '📅 事件查询',
        organization: '🏢 组织查询',
        keywords: '🔤 关键词分析'
      }
      return titles[queryMode.value] || '知识图谱'
    }

    const getEntityIcon = (entity) => {
      if (entity.dgraph_type) {
        if (entity.dgraph_type.includes('Person')) return '👤'
        if (entity.dgraph_type.includes('Organization')) return '🏢'
        if (entity.dgraph_type.includes('Location')) return '📍'
        if (entity.dgraph_type.includes('Event')) return '📅'
      }
      return '🔹'
    }

    const getEntityColor = (entity) => {
      if (entity.dgraph_type) {
        if (entity.dgraph_type.includes('Person')) return '#3b82f6'
        if (entity.dgraph_type.includes('Organization')) return '#8b5cf6'
        if (entity.dgraph_type.includes('Location')) return '#f97316'
        if (entity.dgraph_type.includes('Event')) return '#22c55e'
      }
      return '#888'
    }

    const getEntityTypeName = (entity) => {
      if (!entity.dgraph_type) return '未知'
      if (entity.dgraph_type.includes('Person')) return '人物'
      if (entity.dgraph_type.includes('Organization')) return '组织'
      if (entity.dgraph_type.includes('Location')) return '地点'
      if (entity.dgraph_type.includes('Event')) return '事件'
      return entity.dgraph_type.join(', ')
    }

    const getKeywordSize = (count) => {
      const min = 12, max = 24
      const maxCnt = maxKeywordCount()
      return min + (count / maxCnt) * (max - min)
    }

    const maxKeywordCount = () => {
      if (!keywords.value.length) return 1
      return Math.max(...keywords.value.map(k => k.count))
    }

    // Position keywords in a circular layout, largest in center
    const getKeywordStyle = (keyword, index) => {
      const size = getKeywordSize(keyword.count)
      const maxCnt = maxKeywordCount()
      const normalizedSize = (keyword.count / maxCnt)

      // Use circular layout - most frequent in center
      const total = keywords.value.length
      const centerX = 50 // percent
      const centerY = 50 // percent

      // Calculate radius based on normalized size (larger = closer to center)
      const maxRadius = 38 // percent from center
      const minRadius = 10

      // Spiral outwards from center, most frequent keywords closer to center
      const sortedKeywords = [...keywords.value].sort((a, b) => b.count - a.count)
      const sortedIndex = sortedKeywords.findIndex(k => k.word === keyword.word)

      // Distribute in rings
      const ringSize = Math.ceil(Math.sqrt(total))
      const ring = Math.floor(sortedIndex / ringSize)
      const positionInRing = sortedIndex % ringSize

      const radius = minRadius + (maxRadius - minRadius) * (ring / Math.ceil(total / ringSize))
      const angle = (positionInRing / Math.max(ringSize, 1)) * 2 * Math.PI

      const x = centerX + radius * Math.cos(angle)
      const y = centerY + radius * Math.sin(angle)

      return {
        fontSize: size + 'px',
        position: 'absolute',
        left: x + '%',
        top: y + '%',
        transform: 'translate(-50%, -50%)',
        opacity: 0.5 + normalizedSize * 0.5,
        fontWeight: normalizedSize > 0.7 ? '700' : normalizedSize > 0.4 ? '500' : '400'
      }
    }

    const switchMode = async (mode) => {
      queryMode.value = mode
      searchKeyword.value = ''
      await loadData()
    }

    const loadData = async () => {
      loading.value = true
      try {
        if (queryMode.value === 'overview') {
          await loadOverview()
        } else if (queryMode.value === 'keywords') {
          await loadKeywords()
        } else {
          await searchEntities()
        }
      } catch (e) {
        console.error('KG load error:', e)
      } finally {
        loading.value = false
      }
    }

    const loadOverview = async () => {
      try {
        const response = await kgApi.stats()
        console.log('KG Stats:', response)

        if (response && response.entity_types) {
          entityTypes.value = response.entity_types
        }

        await loadTrends()
        await loadCountryGraph()

      } catch (e) {
        console.error('Overview load error:', e)
      }
    }

    const loadTrends = async () => {
      const days = 7
      const labels = []
      const now = new Date()
      for (let i = days - 1; i >= 0; i--) {
        const d = new Date(now)
        d.setDate(d.getDate() - i)
        labels.push(d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }))
      }

      trendsLabels.value = labels

      entityTypes.value = entityTypes.value.map(type => ({
        ...type,
        trend: labels.map(() => Math.floor(Math.random() * 50) + (type.count || 0) / 7)
      }))
    }

    const loadCountryGraph = async () => {
      try {
        const response = await kgApi.countriesEntities()
        console.log('Country graph data:', response)
        if (response && response.nodes && response.links) {
          graphData.value = response
          await nextTick()
          renderGraph(response.nodes, response.links)
        }
      } catch (e) {
        console.error('Country graph load error:', e)
      }
    }

    const searchEntities = async () => {
      loading.value = true
      try {
        const params = {
          entity_type: queryMode.value,
          limit: 50
        }
        if (searchKeyword.value) {
          params.name = searchKeyword.value
        }

        const response = await kgApi.searchEntities(params)
        console.log('Search results:', response)

        if (response && response.entities) {
          entities.value = response.entities
        } else if (response && response.data) {
          entities.value = response.data
        } else {
          entities.value = []
        }
      } catch (e) {
        console.error('Search error:', e)
        entities.value = []
      } finally {
        loading.value = false
      }
    }

    const selectEntity = (entity) => {
      selectedEntity.value = entity
    }

    // D3 Graph rendering
    const renderGraph = (nodes, links) => {
      if (!svgRef.value || !graphContainer.value || !nodes.length) {
        setTimeout(() => renderGraph(nodes, links), 100)
        return
      }

      const container = graphContainer.value
      const width = container.clientWidth || 800
      const height = 500

      d3.select(svgRef.value).selectAll('*').remove()

      const svg = d3.select(svgRef.value)
        .attr('width', width)
        .attr('height', height)

      const g = svg.append('g')

      const zoom = d3.zoom()
        .scaleExtent([0.2, 3])
        .on('zoom', (event) => g.attr('transform', event.transform))

      svg.call(zoom)

      svg.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '-0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .append('path')
        .attr('d', 'M 0,-5 L 10,0 L 0,5')
        .attr('fill', '#888')

      const nodesCopy = nodes.map(n => ({ ...n }))
      const linksCopy = links.map(l => ({
        source: typeof l.source === 'object' ? l.source.id : l.source,
        target: typeof l.target === 'object' ? l.target.id : l.target,
        weight: l.weight || 1
      }))

      simulation = d3.forceSimulation(nodesCopy)
        .force('link', d3.forceLink(linksCopy).id(d => d.id).distance(100).strength(0.5))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30))

      const link = g.append('g')
        .selectAll('line')
        .data(linksCopy)
        .enter()
        .append('line')
        .attr('class', 'link')
        .attr('stroke', '#888')
        .attr('stroke-opacity', 0.6)
        .attr('stroke-width', d => Math.sqrt(d.weight || 1) + 1)
        .attr('marker-end', 'url(#arrowhead)')

      const node = g.append('g')
        .selectAll('g')
        .data(nodesCopy)
        .enter()
        .append('g')
        .attr('class', 'node')
        .call(d3.drag()
          .on('start', dragstarted)
          .on('drag', dragged)
          .on('end', dragended))

      node.each(function(d) {
        const el = d3.select(this)
        const color = getNodeColor(d.type)

        if (d.type === 'country') {
          el.append('circle').attr('r', 20).attr('fill', color).attr('stroke', '#fff').attr('stroke-width', 2)
        } else if (d.type === 'person') {
          el.append('rect').attr('x', -15).attr('y', -15).attr('width', 30).attr('height', 30).attr('fill', color).attr('stroke', '#fff').attr('stroke-width', 2)
        } else {
          el.append('circle').attr('r', 16).attr('fill', color).attr('stroke', '#fff').attr('stroke-width', 2)
        }
      })

      node.append('text')
        .attr('dy', 35)
        .attr('text-anchor', 'middle')
        .attr('class', 'node-label')
        .attr('fill', 'var(--text-primary)')
        .attr('font-size', '11px')
        .text(d => (d.name || d.id || '').substring(0, 12))

      simulation.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y)
        node.attr('transform', d => `translate(${d.x},${d.y})`)
      })

      function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      }

      function dragged(event, d) {
        d.fx = event.x
        d.fy = event.y
      }

      function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
      }
    }

    const getNodeColor = (type) => {
      const colors = { country: '#f97316', person: '#3b82f6', event: '#22c55e', organization: '#8b5cf6' }
      return colors[type] || '#888'
    }

    const resetZoom = () => {
      if (svgRef.value) {
        d3.select(svgRef.value)
          .transition()
          .duration(750)
          .call(d3.zoom().transform, d3.zoomIdentity)
      }
    }

    const loadKeywords = async () => {
      keywords.value = [
        { word: '中美贸易', count: 156 },
        { word: '关税', count: 134 },
        { word: '科技', count: 98 },
        { word: 'AI', count: 87 },
        { word: '半导体', count: 76 },
        { word: '新能源', count: 65 },
        { word: '美联储', count: 54 },
        { word: '地缘政治', count: 48 },
        { word: '疫情', count: 42 },
        { word: '通胀', count: 38 },
        { word: '大选', count: 35 },
        { word: '气候', count: 28 }
      ]

      const days = 7
      const labels = []
      const now = new Date()
      for (let i = days - 1; i >= 0; i--) {
        const d = new Date(now)
        d.setDate(d.getDate() - i)
        labels.push(d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }))
      }

      keywordTrends.value = {
        labels: labels,
        datasets: [
          {
            label: '中美贸易',
            data: labels.map(() => Math.floor(Math.random() * 30) + 10),
            borderColor: '#ef4444',
            backgroundColor: '#ef444420',
            tension: 0.4,
            fill: true
          },
          {
            label: '关税',
            data: labels.map(() => Math.floor(Math.random() * 25) + 8),
            borderColor: '#f59e0b',
            backgroundColor: '#f59e0b20',
            tension: 0.4,
            fill: true
          },
          {
            label: 'AI',
            data: labels.map(() => Math.floor(Math.random() * 20) + 5),
            borderColor: '#3b82f6',
            backgroundColor: '#3b82f620',
            tension: 0.4,
            fill: true
          }
        ]
      }
    }

    const trendsData = computed(() => ({
      labels: trendsLabels.value,
      datasets: entityTypes.value.map(type => ({
        label: type.name,
        data: type.trend || [],
        borderColor: type.color,
        backgroundColor: type.color + '20',
        tension: 0.4,
        fill: true
      }))
    }))

    const trendsOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { color: 'var(--text-secondary)' }
        }
      },
      scales: {
        x: {
          grid: { color: 'var(--border-color)' },
          ticks: { color: 'var(--text-muted)' }
        },
        y: {
          grid: { color: 'var(--border-color)' },
          ticks: { color: 'var(--text-muted)' }
        }
      }
    }

    const keywordTrendOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { color: 'var(--text-secondary)' }
        }
      },
      scales: {
        x: {
          grid: { color: 'var(--border-color)' },
          ticks: { color: 'var(--text-muted)' }
        },
        y: {
          grid: { color: 'var(--border-color)' },
          ticks: { color: 'var(--text-muted)' }
        }
      }
    }

    onMounted(() => {
      loadData()
    })

    return {
      loading,
      queryMode,
      searchKeyword,
      entities,
      selectedEntity,
      entityTypes,
      keywords,
      graphContainer,
      svgRef,
      trendsData,
      trendsOptions,
      keywordTrends,
      keywordTrendOptions,
      loadData,
      searchEntities,
      switchMode,
      selectEntity,
      resetZoom,
      formatNumber,
      truncate,
      getTypeName,
      getModeTitle,
      getEntityIcon,
      getEntityColor,
      getEntityTypeName,
      getKeywordSize,
      maxKeywordCount,
      getKeywordStyle
    }
  }
}
</script>

<style scoped>
.kg-page {
  display: flex;
  height: calc(100vh - 100px);
  gap: 20px;
}

/* Sidebar */
.kg-sidebar {
  width: 180px;
  flex-shrink: 0;
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 16px 12px;
  border: 1px solid var(--border-color);
  overflow-y: auto;
}

.sidebar-section {
  margin-bottom: 20px;
}

.sidebar-section:last-child {
  margin-bottom: 0;
}

.sidebar-section h4 {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 0 0 8px 8px;
  letter-spacing: 0.5px;
}

.sidebar-section nav {
  display: flex;
  flex-direction: column;
}

.sidebar-section nav a {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.sidebar-section nav a:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.sidebar-section nav a.active {
  background: var(--primary);
  color: white;
}

.sidebar-section nav a .icon {
  font-size: 16px;
  flex-shrink: 0;
}

.sidebar-section nav a .text {
  white-space: nowrap;
}

/* Main Content */
.kg-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
}

.stat-card {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  border: 1px solid var(--border-color);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
}

/* Search */
.search-section {
  padding: 16px;
}

.search-bar {
  display: flex;
  gap: 12px;
}

.search-input {
  flex: 1;
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 14px;
}

/* Entity List */
.entity-list {
  max-height: 400px;
  overflow-y: auto;
}

.entity-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: background 0.2s;
}

.entity-item:hover {
  background: var(--bg-tertiary);
}

.entity-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.entity-info {
  flex: 1;
  min-width: 0;
}

.entity-name {
  font-weight: 500;
  color: var(--text-primary);
  display: block;
}

.entity-desc {
  font-size: 12px;
  color: var(--text-muted);
  display: block;
  margin-top: 2px;
}

.entity-meta {
  flex-shrink: 0;
}

.confidence-badge {
  background: var(--bg-tertiary);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

/* Detail */
.detail-content {
  padding: 16px 0;
}

.detail-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.detail-label {
  color: var(--text-muted);
  font-size: 13px;
  min-width: 60px;
}

.detail-value {
  color: var(--text-primary);
  font-size: 13px;
  flex: 1;
}

/* Keywords Layout */
.keywords-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.keywords-cloud-card {
  min-height: 400px;
}

.keywords-cloud {
  position: relative;
  width: 100%;
  height: 340px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.keyword-tag {
  padding: 6px 14px;
  background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 20px;
  color: rgba(255,255,255,0.7);
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.keyword-tag:hover {
  background: linear-gradient(135deg, rgba(74,222,128,0.2) 0%, rgba(74,222,128,0.05) 100%);
  border-color: rgba(74,222,128,0.3);
  color: #4ade80;
  transform: translate(-50%, -50%) scale(1.1) !important;
  z-index: 10;
}

.keywords-trend {
  height: 400px;
  padding: 16px;
}

.keywords-trend-card {
  min-height: 400px;
}

/* Graph */
.graph-legend {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--bg-tertiary);
  border-radius: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.d3-graph-container {
  position: relative;
  width: 100%;
  height: 450px;
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  border-radius: 12px;
  overflow: hidden;
}

.d3-graph-svg {
  width: 100%;
  height: 100%;
  cursor: grab;
}

.d3-graph-svg:active {
  cursor: grabbing;
}

:deep(.node) {
  cursor: pointer;
}

:deep(.node circle),
:deep(.node rect) {
  transition: all 0.2s;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
}

:deep(.node-label) {
  pointer-events: none;
  font-weight: 500;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

:deep(.link) {
  transition: stroke-opacity 0.2s;
}

.trends-chart {
  height: 250px;
  padding: 16px;
}

.no-data {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}

.result-count {
  font-size: 13px;
  color: var(--text-muted);
}

.btn-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--text-muted);
}

.btn-close:hover {
  color: var(--text-primary);
}

.graph-controls {
  display: flex;
  gap: 8px;
}
</style>
