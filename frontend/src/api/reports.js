import api from './client'
export const getReports = (period = '30d') => api.get('/api/portal/reports/', { params: { period } })
