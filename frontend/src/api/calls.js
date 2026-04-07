import api from './client'
export const getCalls    = (params)     => api.get('/api/portal/calls/', { params })
export const getCall     = (id)         => api.get(`/api/portal/calls/${id}/`)
export const patchCall   = (id, data)   => api.patch(`/api/portal/calls/${id}/`, data)
export const exportCall  = (id)         => api.get(`/api/portal/calls/${id}/export/`, { responseType: 'blob' })
export const deleteCall  = (id)         => api.delete(`/api/portal/calls/${id}/delete/`)
export const deleteAllCalls = ()        => api.delete('/api/portal/calls/delete-all/?confirm=yes')
export const getRealtimeSummary = ()    => api.get('/api/portal/realtime/')
