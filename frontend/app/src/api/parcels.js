import client from './client'

export const registerParcel = (data) => client.post('/api/parcels/register/', data)
export const scanParcel = (data) => client.post('/api/parcels/scan/', data)
export const trackParcel = async (code) => (await client.get(`/api/parcels/track/${code}/`)).data
export const getParcels = async (status) => (await client.get(`/api/parcels/${status ? `?status=${status}` : ''}`)).data