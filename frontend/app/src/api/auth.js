import client from './client'

export const login = (username, password) =>
  client.post('/api/auth/token/', { username, password }).then((res) => res.data)

export const refreshToken = (refresh) =>
  client.post('/api/auth/token/refresh/', { refresh }).then((res) => res.data)

export const deviceHandshake = (device_uuid) =>
  client.post('/api/auth/device/handshake/', { device_uuid }).then((res) => res.data)

export const requestDeviceMigration = (phone_number, device_uuid) =>
  client.post('/api/auth/device/migration/request/', { phone_number, device_uuid }).then((res) => res.data)

export const verifyDeviceMigration = (token) =>
  client.post('/api/auth/device/migration/verify/', { token }).then((res) => res.data)

export const getProfileStatus = () =>
  client.get('/api/auth/commuter/profile/status/').then((res) => res.data)

export const updateProfile = (first_name, last_name) =>
  client.post('/api/auth/commuter/profile/update/', { first_name, last_name }).then((res) => res.data)