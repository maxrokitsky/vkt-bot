import { client } from './client/client.gen'

// Configure client with base URL and auth interceptor
client.setConfig({
  baseUrl: 'http://localhost:8000',
})

// Add request interceptor to include auth token
client.interceptors.request.use((request: Request) => {
  const token = localStorage.getItem('token')
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`)
  }
  return request
})
