import client from './client'

export const getTrips = () => client.get('/api/routing/commuter/trips/')
export const getTrip = (id) => client.get(`/api/routing/commuter/trips/${id}/`)
export const getDriverTrips = () => client.get('/api/routing/driver/trips/')
export const getDriverTrip = (id) => client.get(`/api/routing/driver/trips/${id}/`)
export const getSeatAvailability = (stopId) =>
  client.get(`/api/routing/stops/${stopId}/seat-availability/`)
export const getTripStops = (tripId) => client.get(`/api/routing/commuter/trips/${tripId}/stops/`)
export const getStops = () => client.get('/api/routing/stops/list/')

export const findRide = (lat, lng, destinationStopId) =>
  client.get(`/api/routing/find-ride/?lat=${lat}&lng=${lng}${destinationStopId ? `&destination=${destinationStopId}` : ''}`)

export const getNearbyRoutes = (lat, lng) =>
  client.get(`/api/routing/nearby-routes/?lat=${lat}&lng=${lng}`)

export const findLinkedJourney = (lat, lng, finalDestinationId) =>
  client.get(`/api/routing/find-linked-journey/?lat=${lat}&lng=${lng}&final_destination=${finalDestinationId}`)