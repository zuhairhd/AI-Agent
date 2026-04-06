import api from './client'
export const getAlerts    = (params) => api.get('/api/portal/alerts/', { params })
export const patchAlert   = (id, data) => api.patch(`/api/portal/alerts/${id}/`, data)
export const resendEmail  = (id) => api.post(`/api/portal/alerts/${id}/resend-email/`)
