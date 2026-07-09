import client from './client'

export const getFleets = () => client.get('/api/fleet/fleets/').then(res => res.data)
export const getVehicles = () => client.get('/api/fleet/vehicles/').then(res => res.data)
export const createVehicle = (data) => client.post('/api/fleet/vehicles/', data).then(res => res.data)
export const updateVehicle = (id, data) => client.patch(`/api/fleet/vehicles/${id}/`, data).then(res => res.data)
export const getLiveFleet = async () => (await client.get('/api/fleet/live/')).data
export const getAnalytics = async (start, end) => (await client.get(`/api/fleet/analytics/?start=${start}&end=${end}`)).data
export const getDocumentAlerts = async () => (await client.get('/api/fleet/document-alerts/')).data
export const exportFinancials = (start, end) =>
  client.get(`/api/fleet/export/?start=${start}&end=${end}`, { responseType: 'blob' })