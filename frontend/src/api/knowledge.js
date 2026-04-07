import api from './client'
export const getKnowledge   = (params) => api.get('/api/portal/knowledge/', { params })
export const uploadKnowledge = (formData) => api.post('/api/portal/knowledge/upload/', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
export const deleteKnowledge = (id) => api.delete(`/api/portal/knowledge/${id}/delete/`)
export const resyncKnowledge = (id) => api.post(`/api/portal/knowledge/${id}/resync/`)
