import client from './client'

export const postPosition = (payload) =>
  client.post('/api/telemetry/position/', payload)
