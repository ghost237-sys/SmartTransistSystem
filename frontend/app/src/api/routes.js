import client from './client'

export const getRoutes = () => client.get('/api/routing/routes/').then(res => res.data)
export const createRoute = (data) => client.post('/api/routing/routes/', data).then(res => res.data)
export const deleteRoute = (id) => client.delete(`/api/routing/routes/${id}/`).then(res => res.data)
export const updateRoute = (id, data) => client.patch(`/api/routing/routes/${id}/`, data).then(res => res.data)

export const findRide = (params) => client.get('/api/routing/find-ride/', { params }).then(res => res.data)
export const findLinkedJourney = (params) => client.get('/api/routing/find-linked-journey/', { params }).then(res => res.data)
export const getNearbyRoutes = (params) => client.get('/api/routing/nearby-routes/', { params }).then(res => res.data)
