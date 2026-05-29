<template>
  <div class="config">
    <div class="config-header">
      <div class="header-left">
        <h2>System Configuration</h2>
        <span class="header-subtitle">Manage runtime settings and overrides</span>
      </div>
      <div class="header-actions">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Filter configs..."
            class="search-input"
          />
          <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">✕</button>
        </div>
        <button class="btn btn-outline" @click="reloadAll" :disabled="loading">
          {{ loading ? 'Loading...' : 'Reload All' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-error" @click="error = null">
      <span class="alert-icon">⚠️</span>
      <span>{{ error }}</span>
      <button class="alert-close">✕</button>
    </div>

    <div v-if="loading && !configLoaded" class="loading-state">
      <div class="spinner"></div>
      <span>Loading configuration...</span>
    </div>

    <template v-else>
      <div class="section-tabs">
        <button
          v-for="section in sections"
          :key="section.name"
          class="tab-btn"
          :class="{ active: activeSection === section.name }"
          @click="selectSection(section.name)"
        >
          <span class="tab-icon">{{ section.icon }}</span>
          <span class="tab-label">{{ section.label }}</span>
          <span class="tab-badge" v-if="section.count > 0">{{ section.count }}</span>
        </button>
      </div>

      <div class="config-card">
        <div class="card-header">
          <div class="card-header-left">
            <span class="section-icon">{{ activeSectionInfo?.icon || '⚙️' }}</span>
            <h3>{{ activeSectionInfo?.label || activeSection }}</h3>
            <span class="item-badge">{{ filteredItems.length }} / {{ configItems.length }} items</span>
          </div>
          <div class="card-header-right">
            <button class="btn btn-sm btn-outline" @click="expandAll" v-if="configItems.length > 0">
              {{ allExpanded ? 'Collapse All' : 'Expand All' }}
            </button>
            <button class="btn btn-sm" @click="showAddForm = !showAddForm">
              {{ showAddForm ? 'Cancel' : '+ Add Item' }}
            </button>
          </div>
        </div>

        <div v-if="saving" class="toast-saving">
          <span class="spinner-sm"></span> Saving...
        </div>

        <div v-if="filteredItems.length === 0" class="empty-state">
          <span class="empty-icon">{{ searchQuery ? '🔍' : '📭' }}</span>
          <p>{{ searchQuery ? 'No configs match your search.' : 'No configuration items in this section.' }}</p>
          <p v-if="!searchQuery" class="empty-hint">Click "+ Add Item" to create one.</p>
        </div>

        <div v-else class="config-list">
          <div
            v-for="item in filteredItems"
            :key="item.id || item.key"
            class="config-item"
            :class="{
              'config-item-expanded': allExpanded || editingKey === item.key,
              'config-item-db': isDbOverride(item)
            }"
          >
            <div class="config-item-header" @click="toggleExpand(item)">
              <div class="config-item-left">
                <span class="expand-arrow">{{ (allExpanded || editingKey === item.key) ? '▾' : '▸' }}</span>
                <code class="config-key-text">{{ item.key }}</code>
                <span :class="['type-tag', 'type-' + (item.value_type || 'string')]">
                  {{ item.value_type || 'string' }}
                </span>
              </div>
              <div class="config-item-right">
                <span :class="isDbOverride(item) ? 'source-badge db' : 'source-badge default'">
                  {{ isDbOverride(item) ? 'DB Override' : 'Default' }}
                </span>
                <span class="value-preview">{{ truncateValue(item) }}</span>
              </div>
            </div>

            <div v-if="(allExpanded || editingKey === item.key)" class="config-item-body">
              <div class="edit-row">
                <div class="edit-field" v-if="item.value_type === 'bool'">
                  <label class="switch">
                    <input
                      type="checkbox"
                      :checked="parseBool(item.value)"
                      @change="toggleBool(item)"
                    />
                    <span class="switch-slider"></span>
                  </label>
                  <span class="switch-label">{{ parseBool(item.value) ? 'Enabled' : 'Disabled' }}</span>
                </div>

                <div class="edit-field full" v-else-if="item.value_type === 'int' || item.value_type === 'float'">
                  <label>Value</label>
                  <input
                    type="number"
                    :value="item.value_type === 'float' ? parseFloat(item.value) : parseInt(item.value)"
                    @change="updateValue(item, $event.target.value)"
                    class="form-input"
                    :step="item.value_type === 'float' ? '0.01' : '1'"
                  />
                </div>

                <div class="edit-field full" v-else-if="item.value_type === 'json'">
                  <label>Value (JSON)</label>
                  <textarea
                    :value="formatJsonValue(item.value)"
                    @change="updateValue(item, $event.target.value)"
                    class="form-input form-textarea form-textarea-json"
                    rows="6"
                  />
                </div>

                <div class="edit-field full" v-else-if="isLongString(item.value)">
                  <label>Value</label>
                  <textarea
                    :value="item.value"
                    @change="updateValue(item, $event.target.value)"
                    class="form-input form-textarea"
                    rows="5"
                  />
                </div>

                <div class="edit-field full" v-else>
                  <label>Value</label>
                  <input
                    type="text"
                    :value="item.value"
                    @change="updateValue(item, $event.target.value)"
                    class="form-input"
                  />
                </div>
              </div>

              <div class="edit-row">
                <div class="edit-field">
                  <label>Description</label>
                  <input
                    type="text"
                    :value="item.description || ''"
                    @change="item.description = $event.target.value"
                    class="form-input"
                    placeholder="Optional description"
                  />
                </div>
              </div>

              <div class="config-item-actions">
                <span class="config-meta">{{ item.description || 'No description' }}</span>
                <div class="action-btns">
                  <button class="btn btn-sm btn-primary" @click="saveEdit(item)" :disabled="saving">
                    Save
                  </button>
                  <button
                    v-if="isDbOverride(item)"
                    class="btn btn-sm btn-danger"
                    @click="deleteItem(item)"
                    :disabled="saving"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="showAddForm" class="add-section fade-in">
          <div class="add-section-header">
            <span class="add-icon">➕</span>
            <h4>Add Configuration to "{{ activeSectionInfo?.label || activeSection }}"</h4>
          </div>
          <div class="add-form">
            <div class="form-row">
              <div class="form-field">
                <label>Key <span class="required">*</span></label>
                <input
                  v-model="newItem.key"
                  type="text"
                  placeholder="e.g., CUSTOM_THRESHOLD"
                  class="form-input"
                />
              </div>
              <div class="form-field">
                <label>Type</label>
                <select v-model="newItem.value_type" class="form-input">
                  <option value="string">String</option>
                  <option value="int">Integer</option>
                  <option value="float">Float</option>
                  <option value="bool">Boolean</option>
                  <option value="json">JSON</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-field flex-1">
                <label>Value <span class="required">*</span></label>
                <input
                  v-model="newItem.value"
                  type="text"
                  placeholder="Value"
                  class="form-input"
                />
              </div>
              <div class="form-field flex-2">
                <label>Description</label>
                <input
                  v-model="newItem.description"
                  type="text"
                  placeholder="Optional description"
                  class="form-input"
                />
              </div>
            </div>
            <div class="form-actions">
              <button class="btn btn-primary" @click="addItem" :disabled="!newItem.key || !newItem.value || saving">
                {{ saving ? 'Adding...' : 'Add Configuration' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { configApi } from '../api'

export default {
  name: 'Config',
  setup() {
    const loading = ref(true)
    const saving = ref(false)
    const error = ref(null)
    const configLoaded = ref(false)
    const allConfig = ref({})
    const activeSection = ref('breaking')
    const editingKey = ref(null)
    const searchQuery = ref('')
    const showAddForm = ref(false)
    const allExpanded = ref(false)

    const newItem = ref({
      key: '',
      value: '',
      value_type: 'string',
      description: ''
    })

    const sectionDefinitions = {
      breaking: { label: 'Breaking News', icon: '🚨', order: 1 },
      twitter: { label: 'Twitter Alerts', icon: '🐦', order: 2 },
      notifications: { label: 'Notifications', icon: '🔔', order: 3 },
      scheduler: { label: 'Scheduler', icon: '⏰', order: 4 },
      astock: { label: 'A-Stock', icon: '📈', order: 5 },
      database: { label: 'Database', icon: '💾', order: 6 },
      redis: { label: 'Redis', icon: '🔴', order: 7 },
      llm: { label: 'LLM', icon: '🤖', order: 8 },
      ragflow: { label: 'RAGFlow', icon: '📚', order: 9 },
      knowledge_graph: { label: 'Knowledge Graph', icon: '🔗', order: 10 },
      prompts: { label: 'Prompts', icon: '💬', order: 11 },
      general: { label: 'General', icon: '⚙️', order: 99 },
    }

    const sections = computed(() => {
      const names = Object.keys(allConfig.value)
      return names
        .map(name => ({
          name,
          label: sectionDefinitions[name]?.label || name,
          icon: sectionDefinitions[name]?.icon || '📄',
          order: sectionDefinitions[name]?.order || 50,
          count: (allConfig.value[name] || []).length
        }))
        .sort((a, b) => a.order - b.order)
    })

    const activeSectionInfo = computed(() =>
      sections.value.find(s => s.name === activeSection.value)
    )

    const configItems = computed(() => {
      const items = allConfig.value[activeSection.value] || []
      return items.map(item => ({
        ...item,
        _isDbOverride: item.source === 'db' || !item.source
      }))
    })

    const filteredItems = computed(() => {
      if (!searchQuery.value) return configItems.value
      const q = searchQuery.value.toLowerCase()
      return configItems.value.filter(item =>
        item.key.toLowerCase().includes(q) ||
        (item.description || '').toLowerCase().includes(q) ||
        String(item.value).toLowerCase().includes(q)
      )
    })

    const isDbOverride = (item) => item._isDbOverride || item.source === 'db'

    const toggleExpand = (item) => {
      if (editingKey.value === item.key) {
        editingKey.value = null
      } else {
        editingKey.value = item.key
      }
    }

    const expandAll = () => {
      allExpanded.value = !allExpanded.value
      if (!allExpanded.value) editingKey.value = null
    }

    const loadConfig = async () => {
      loading.value = true
      error.value = null
      try {
        const data = await configApi.getAll()
        allConfig.value = data.config || {}
        if (sections.value.length > 0 && !sections.value.find(s => s.name === activeSection.value)) {
          activeSection.value = sections.value[0].name
        }
        configLoaded.value = true
      } catch (e) {
        error.value = e.message || 'Failed to load configuration'
      } finally {
        loading.value = false
      }
    }

    const reloadAll = async () => {
      loading.value = true
      try {
        await configApi.reloadConfig()
        await loadConfig()
      } catch (e) {
        error.value = e.message || 'Failed to reload'
      } finally {
        loading.value = false
      }
    }

    const selectSection = (name) => {
      activeSection.value = name
      editingKey.value = null
      searchQuery.value = ''
      showAddForm.value = false
    }

    const saveEdit = async (item) => {
      saving.value = true
      try {
        await configApi.updateSection(activeSection.value, [{
          key: item.key,
          value: item.value,
          value_type: item.value_type,
          description: item.description
        }])
        await loadConfig()
        editingKey.value = null
      } catch (e) {
        error.value = e.message || 'Failed to save'
      } finally {
        saving.value = false
      }
    }

    const updateValue = (item, newValue) => { item.value = newValue }
    const toggleBool = (item) => {
      item.value = (item.value === 'true' || item.value === true) ? 'false' : 'true'
    }

    const parseBool = (value) => {
      if (typeof value === 'boolean') return value
      return value === 'true' || value === '1' || value === 'yes'
    }

    const deleteItem = async (item) => {
      if (!confirm(`Remove override for "${item.key}"?\nIt will revert to default value.`)) return
      saving.value = true
      try {
        await configApi.delete(activeSection.value, item.key)
        await loadConfig()
      } catch (e) {
        error.value = e.message || 'Failed to delete'
      } finally {
        saving.value = false
      }
    }

    const addItem = async () => {
      saving.value = true
      try {
        await configApi.create(
          activeSection.value,
          newItem.value.key,
          newItem.value.value,
          newItem.value.value_type,
          newItem.value.description
        )
        newItem.value = { key: '', value: '', value_type: 'string', description: '' }
        showAddForm.value = false
        await loadConfig()
      } catch (e) {
        error.value = e.message || 'Failed to add'
      } finally {
        saving.value = false
      }
    }

    const formatJsonValue = (value) => {
      try {
        return JSON.stringify(JSON.parse(value), null, 2)
      } catch { return value }
    }

    const isLongString = (value) => {
      if (!value) return false
      return value.length > 200 || value.includes('\n')
    }

    const truncateValue = (item) => {
      const val = String(item.value || '')
      if (val.length <= 40) return val
      return val.substring(0, 40) + '...'
    }

    watch(activeSection, () => { editingKey.value = null; searchQuery.value = ''; showAddForm.value = false })

    onMounted(() => loadConfig())

    return {
      loading, saving, error, configLoaded, sections, activeSection,
      activeSectionInfo, configItems, filteredItems, editingKey, searchQuery,
      showAddForm, allExpanded, newItem,
      isDbOverride, toggleExpand, expandAll,
      loadConfig, reloadAll, selectSection, saveEdit, updateValue,
      toggleBool, parseBool, deleteItem, addItem,
      formatJsonValue, isLongString, truncateValue
    }
  }
}
</script>

<style scoped>
.config {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.header-left h2 {
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-subtitle {
  font-size: 13px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Search */
.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  font-size: 14px;
  pointer-events: none;
}

.search-input {
  width: 200px;
  padding: 7px 28px 7px 32px;
  border: 1px solid var(--border-color-dark);
  border-radius: 6px;
  font-size: 13px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.search-input::placeholder { color: var(--text-muted); }

.search-clear {
  position: absolute;
  right: 6px;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 6px;
}

.search-clear:hover { color: var(--text-primary); }

/* Alert */
.alert {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  cursor: pointer;
  animation: fadeIn 0.3s ease-out;
}

.alert-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.alert-icon { font-size: 16px; }
.alert-close {
  margin-left: auto;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 14px;
}

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-muted);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner-sm {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 6px;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Tabs */
.section-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 20px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--border-color-dark);
  border-radius: 20px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
  white-space: nowrap;
}

.tab-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.tab-btn.active {
  background: var(--accent);
  color: #1a1a2e;
  border-color: var(--accent);
  font-weight: 600;
}

.tab-icon { font-size: 15px; }

.tab-badge {
  background: rgba(0, 0, 0, 0.1);
  color: inherit;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  min-width: 20px;
  text-align: center;
}

.tab-btn.active .tab-badge {
  background: rgba(0, 0, 0, 0.2);
}

/* Card */
.config-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 2px 12px var(--shadow);
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
  gap: 12px;
}

.card-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-icon { font-size: 20px; }

.card-header-left h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.item-badge {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 2px 10px;
  border-radius: 10px;
}

.card-header-right {
  display: flex;
  gap: 8px;
}

/* Toast */
.toast-saving {
  margin: 0 20px;
  padding: 8px 14px;
  background: var(--accent);
  color: #1a1a2e;
  border-radius: 0 0 8px 8px;
  font-size: 13px;
  font-weight: 600;
  animation: fadeIn 0.2s ease-out;
}

/* Empty */
.empty-state {
  padding: 60px 20px;
  text-align: center;
}

.empty-icon { font-size: 40px; display: block; margin-bottom: 12px; }
.empty-state p { color: var(--text-muted); margin: 4px 0; }
.empty-hint { font-size: 13px; }

/* List */
.config-list {
  display: flex;
  flex-direction: column;
}

.config-item {
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
}

.config-item:last-child { border-bottom: none; }
.config-item:hover { background: rgba(74, 222, 128, 0.03); }

.config-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  cursor: pointer;
  gap: 12px;
  flex-wrap: wrap;
}

.config-item-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.expand-arrow {
  font-size: 12px;
  color: var(--text-muted);
  width: 16px;
  flex-shrink: 0;
}

.config-key-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}

.type-tag {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.type-string  { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
.type-int     { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.type-float   { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.type-bool    { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.type-json    { background: rgba(139, 92, 246, 0.15); color: #8b5cf6; }

.config-item-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.source-badge {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
}
.source-badge.db      { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.source-badge.default { background: rgba(107, 114, 128, 0.15); color: #6b7280; }

.value-preview {
  font-size: 12px;
  color: var(--text-muted);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}

/* Expanded body */
.config-item-body {
  padding: 0 20px 16px 20px;
  border-top: 1px solid var(--border-color);
  animation: fadeIn 0.15s ease-out;
}

.edit-row {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
}

.edit-field.full { flex: 1; min-width: 200px; }

.edit-field label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.required { color: #ef4444; }

.form-input {
  padding: 8px 12px;
  border: 1px solid var(--border-color-dark);
  border-radius: 6px;
  font-size: 13px;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: border-color 0.2s, box-shadow 0.2s;
  width: 100%;
  box-sizing: border-box;
  font-family: inherit;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.form-input::placeholder { color: var(--text-muted); }

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.form-textarea-json {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
}

select.form-input {
  cursor: pointer;
  appearance: auto;
}

/* Switch */
.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.switch input { opacity: 0; width: 0; height: 0; }

.switch-slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background: var(--border-color-dark);
  border-radius: 24px;
  transition: background 0.2s;
}

.switch-slider::before {
  content: '';
  position: absolute;
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s;
}

.switch input:checked + .switch-slider { background: var(--accent); }
.switch input:checked + .switch-slider::before { transform: translateX(20px); }

.switch-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-left: 8px;
}

/* Actions */
.config-item-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  flex-wrap: wrap;
  gap: 8px;
}

.config-meta {
  font-size: 12px;
  color: var(--text-muted);
  flex: 1;
  min-width: 150px;
}

.action-btns { display: flex; gap: 8px; }

/* Add section */
.add-section {
  margin: 0 20px 20px;
  padding: 20px;
  background: var(--bg-tertiary);
  border-radius: 10px;
  border: 1px dashed var(--border-color-dark);
}

.add-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.add-section-header h4 { margin: 0; font-size: 14px; color: var(--text-primary); }
.add-icon { font-size: 16px; }

.add-form { display: flex; flex-direction: column; gap: 12px; }

.form-row { display: flex; gap: 12px; flex-wrap: wrap; }

.form-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 140px;
}

.form-field.flex-1 { flex: 1; }
.form-field.flex-2 { flex: 2; }

.form-field label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.form-actions { display: flex; justify-content: flex-end; }

/* Buttons */
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.btn-primary { background: var(--accent); color: #1a1a2e; }
.btn-primary:hover { filter: brightness(1.1); }

.btn-outline {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color-dark);
}
.btn-outline:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.btn-danger { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.btn-danger:hover { background: rgba(239, 68, 68, 0.2); }

.btn-sm { padding: 5px 10px; font-size: 12px; }

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Animations */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-in { animation: fadeIn 0.2s ease-out; }

@media (max-width: 768px) {
  .config { padding: 12px; }
  .header-actions { width: 100%; flex-wrap: wrap; }
  .search-input { width: 140px; }
  .section-tabs { overflow-x: auto; flex-wrap: nowrap; padding-bottom: 8px; }
  .tab-btn { flex-shrink: 0; }
  .config-item-right { display: none; }
  .config-key-text { max-width: 160px; }
  .form-row { flex-direction: column; }
  .form-field { width: 100%; }
}
</style>
