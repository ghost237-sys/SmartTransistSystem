import client from './client'

export const login = (username, password) =>
  client.post('/api/auth/token/', { username, password }).then((res) => res.data)

export const refreshToken = (refresh) =>
  client.post('/api/auth/token/refresh/', { refresh }).then((res) => res.data)