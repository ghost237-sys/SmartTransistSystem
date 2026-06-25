import client from './client'

export const getTrips = () => client.get('/api/routing/commuter/trips/')
export const getTrip = (id) => client.get(`/api/routing/commuter/trips/${id}/`)
export const getDriverTrips = () => client.get('/api/routing/driver/trips/')
export const getDriverTrip = (id) => client.get(`/api/routing/driver/trips/${id}/`)
export const getSeatAvailability = (stopId) =>
  client.get(`/api/routing/stops/${stopId}/seat-availability/`)
export const getTripStops = (tripId) => client.get(`/api/routing/commuter/trips/${tripId}/stops/`)