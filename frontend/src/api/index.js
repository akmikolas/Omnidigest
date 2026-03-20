import axios from 'axios'

// 开发环境: 通过 Vite 代理 /api -> localhost:7080
// 生产环境: 设置 VITE_API_URL 环境变量
const apiBaseURL = import.meta?.env?.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: apiBaseURL,
  timeout: 10000, // 10 秒超时
  headers: {
    'Content-Type': 'application/json'
  }
})

// Add API key to all requests
api.interceptors.request.use(config => {
  const apiKey = localStorage.getItem('api_key')
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
    console.log('API key added to request:', config.url)
  } else {
    console.log('No API key found for request:', config.url)
  }
  return config
})

// Handle errors
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('api_key')
      // Dispatch custom event for API key prompt
      window.dispatchEvent(new CustomEvent('api-key-required', {
        detail: { message: 'Invalid API Key. Please enter your API key (format: client_name:key):' }
      }))
    }
    // Handle timeout
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      error.message = '请求超时，请检查后端服务是否正常运行'
    }
    return Promise.reject(error)
  }
)

// Stats API
export const statsApi = {
  overview: () => api.get('/stats/overview'),
  articles: (days = 7) => api.get(`/stats/articles?days=${days}`),
  breaking: (days = 7) => api.get(`/stats/breaking?days=${days}`),
  twitter: (days = 7) => api.get(`/stats/twitter?days=${days}`),
  llm: (hours = 168, startDate = null, endDate = null) => {
    let params = []
    if (startDate && endDate) {
      params.push(`start_date=${startDate}`)
      params.push(`end_date=${endDate}`)
    } else if (hours) {
      params.push(`hours=${hours}`)
    }
    return api.get(`/stats/llm?${params.join('&')}`)
  },
  tokenStats: (days = 30) => api.get(`/token-stats?days=${days}`),
  tokenStatsByRange: (startDate = null, endDate = null, hours = null) => {
    let url = '/token-stats/range?'
    if (hours) {
      url += `hours=${hours}`
    } else if (startDate && endDate) {
      url += `start_date=${startDate}&end_date=${endDate}`
    } else {
      url += 'hours=24'
    }
    return api.get(url)
  },
  tokenStatsTimeline: (startDate = null, endDate = null, hours = null) => {
    let url = '/token-stats/timeline?'
    if (hours) {
      url += `hours=${hours}`
    } else if (startDate && endDate) {
      url += `start_date=${startDate}&end_date=${endDate}`
    } else {
      url += 'hours=168'
    }
    return api.get(url)
  }
}

// Config API
export const configApi = {
  getAll: () => api.get('/config'),
  getSection: (section) => api.get(`/config/${section}`),
  getValue: (section, key) => api.get(`/config/${section}/${key}`),
  updateSection: (section, items) => api.put(`/config/${section}`, items),
  create: (section, key, value, valueType = 'string', description = '') =>
    api.post('/config', { section, key, value, valueType, description }),
  delete: (section, key) => api.delete(`/config/${section}/${key}`)
}

// Sources API
export const sourcesApi = {
  list: (serviceType = 'daily', enabled = null) => {
    let url = `/sources?service_type=${serviceType}`
    if (enabled !== null) {
      url += `&enabled=${enabled}`
    }
    return api.get(url)
  },
  listAll: (enabled = null) => {
    const url = enabled !== null ? `/sources/rss?enabled=${enabled}` : '/sources/rss'
    return api.get(url)
  },
  add: (url, name) => api.post('/sources/rss', null, { params: { url, name } }),
  update: (id, data) => api.put(`/sources/rss/${id}`, data),
  delete: (id) => api.delete(`/sources/rss/${id}`),
  toggle: (id) => api.post(`/sources/rss/${id}/toggle`)
}

// Auth API
export const authApi = {
  listKeys: () => api.get('/auth/keys'),
  createKey: (clientName) => api.post('/auth/keys', null, { params: { client_name: clientName } }),
  revokeKey: (clientName) => api.delete(`/auth/keys/${clientName}`),
  activateKey: (clientName) => api.post(`/auth/keys/${clientName}/activate`)
}

// Knowledge Graph API
export const kgApi = {
  status: () => api.get('/kg/status'),
  stats: () => api.get('/kg/stats'),
  // Search entities with filters
  searchEntities: (params) => api.get('/kg/entities', { params }),
  // Get entity details by UID
  getEntity: (uid) => api.get(`/kg/entity/${uid}`),
  // Query relations with filters
  getRelations: (params) => api.get('/kg/relations', { params }),
  // Search path between entities
  searchPath: (params) => api.get('/kg/search', { params })
}

// A-Stock Analysis API
export const astockApi = {
  // 实时行情
  quotes: () => api.get('/astock/quotes'),
  // 板块涨跌排行
  sectors: () => api.get('/astock/sectors'),
  // 财经新闻列表
  news: (limit = 20) => api.get(`/astock/news?limit=${limit}`),
  // 最新分析结果
  latestAnalysis: () => api.get('/astock/analysis/latest'),
  // 历史预测
  predictions: (days = 30) => api.get(`/astock/predictions?days=${days}`),
  // 准确率统计
  accuracy: () => api.get('/astock/accuracy'),
  // 手动触发分析
  triggerAnalysis: () => api.post('/astock/analysis/trigger'),
  // 个股行情
  stockQuote: (symbol) => api.get(`/astock/stocks/${symbol}`),
  // 个股新闻
  stockNews: (symbol, limit = 20) => api.get(`/astock/stocks/${symbol}/news?limit=${limit}`)
}

export default api
