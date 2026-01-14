import { client } from './client/client.gen'

// Configure client with base URL and auth interceptor
client.setConfig({
  baseUrl: 'http://localhost:8765',
})

// Add request interceptor to include auth token
client.interceptors.request.use((request: Request) => {
  const url = new URL(request.url)
  // Don't add auth header to login endpoint
  if (url.pathname === '/api/auth/login') {
    return request
  }
  const token = localStorage.getItem('token')
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`)
  }
  return request
})
