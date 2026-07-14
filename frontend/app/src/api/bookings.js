import client from './client'

export const createBooking = (data) => client.post('/api/bookings/create/', data)
export const getBooking = async (bookingId) => (await client.get(`/api/bookings/${bookingId}/`)).data
export const getBookingPickupStatus = async (bookingId) =>
  (await client.get(`/api/bookings/${bookingId}/pickup-status/`)).data
export const getMyBookings = async () => (await client.get('/api/bookings/my/')).data
export const verifyTicket = (data) => client.post('/api/bookings/verify-ticket/', data)
export const recordCashPayment = (data) => client.post('/api/bookings/cash-payment/', data)
export const getTripManifest = async (tripId) => (await client.get(`/api/bookings/trips/${tripId}/manifest/`)).data
export const departTrip = (tripId) => client.post(`/api/bookings/trips/${tripId}/depart/`)
export const completeTrip = (tripId) => client.post(`/api/bookings/trips/${tripId}/complete/`)
export const createMultiModeBooking = (data) => client.post('/api/bookings/multi-mode/', data)