import client from './client'

export const getFleets = () => client.get('/api/fleet/fleets/')
export const getVehicles = () => client.get('/api/fleet/vehicles/')
export const getLiveFleet = async () => (await client.get('/api/fleet/live/')).data
export const getAnalytics = async (start, end) => (await client.get(`/api/fleet/analytics/?start=${start}&end=${end}`)).data
export const getDocumentAlerts = async () => (await client.get('/api/fleet/document-alerts/')).data
export const exportFinancials = (start, end) =>
  client.get(`/api/fleet/export/?start=${start}&end=${end}`, { responseType: 'blob' })