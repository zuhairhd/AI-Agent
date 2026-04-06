import api from './client'

export const login   = (username, password) => api.post('/api/portal/auth/login/', { username, password })
export const logout  = ()                   => api.post('/api/portal/auth/logout/')
export const me      = ()                   => api.get('/api/portal/auth/me/')
