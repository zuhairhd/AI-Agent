import api from './client'
export const getFollowUps    = (params) => api.get('/api/portal/followups/', { params })
export const createFollowUp  = (data)   => api.post('/api/portal/followups/', data)
export const patchFollowUp   = (id, data) => api.patch(`/api/portal/followups/${id}/`, data)
