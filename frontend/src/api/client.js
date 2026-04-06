import axios from 'axios'

function getCsrfToken() {
  const name = 'csrftoken'
  const cookies = document.cookie.split(';')
  for (const cookie of cookies) {
    const [k, v] = cookie.trim().split('=')
    if (k === name) return decodeURIComponent(v)
  }
  return ''
}

const api = axios.create({
  baseURL: '/',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(config => {
  config.headers['X-CSRFToken'] = getCsrfToken()
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      window.location.href = '/portal/login'
    }
    return Promise.reject(err)
  }
)

export default api
