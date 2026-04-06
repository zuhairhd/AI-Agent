import api from './client'
export const getCalls  = (params) => api.get('/api/portal/calls/', { params })
export const getCall   = (id)     => api.get(`/api/portal/calls/${id}/`)
export const patchCall = (id, data) => api.patch(`/api/portal/calls/${id}/`, data)
