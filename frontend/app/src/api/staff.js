import client from './client'

export const getStaff = (role) => client.get(`/api/accounts/staff/?role=${role}`).then(res => res.data)
export const createStaff = (data) => client.post('/api/accounts/staff/', data).then(res => res.data)
export const deleteStaff = (id) => client.delete(`/api/accounts/staff/${id}/`).then(res => res.data)
export const updateStaff = (id, data) => client.patch(`/api/accounts/staff/${id}/`, data).then(res => res.data)
