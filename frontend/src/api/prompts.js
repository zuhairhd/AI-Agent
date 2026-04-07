import api from './client'
export const getPrompts       = ()          => api.get('/api/portal/prompts/')
export const getPrompt        = (stem)      => api.get(`/api/portal/prompts/${stem}/`)
export const updatePrompt     = (stem, data) => api.put(`/api/portal/prompts/${stem}/`, data)
export const regeneratePrompt = (stem)      => api.post(`/api/portal/prompts/${stem}/regenerate/`)
export const uploadPromptAudio = (stem, formData) => api.post(
  `/api/portal/prompts/${stem}/upload-audio/`, formData,
  { headers: { 'Content-Type': 'multipart/form-data' } },
)
