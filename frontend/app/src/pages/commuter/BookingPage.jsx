import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getTrip, getTripStops } from '../../api/trips'
import { createBooking, getBooking } from '../../api/bookings'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import TicketDisplay from '../../components/TicketDisplay'

function formatDateTime(datetime) {
  return new Date(datetime).toLocaleString('en-KE', {
    weekday: 'long', day: 'numeric', month: 'long',
    hour: '2-digit', minute: '2-digit', hour12: true
  })
}

export default function BookingPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()

  const [phone, setPhone] = useState('')
  const [alightingStopId, setAlightingStopId] = useState('')
  const [loading, setLoading] = useState(false)
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState('')

  const { data: trip, isLoading: loadingTrip } = useQuery({
    queryKey: ['trip', tripId],
    queryFn: async () => (await getTrip(tripId)).data,
  })

  const { data: stops, isLoading: loadingStops } = useQuery({
    queryKey: ['trip-stops', tripId],
    queryFn: async () => (await getTripStops(tripId)).data,
  })

  useEffect(() => {
    if (!booking?.id || booking.status === 'confirmed' || booking.status === 'boarded') {
      return undefined
    }

    if (['cancelled', 'expired'].includes(booking.status)) {
      return undefined
    }

    const interval = setInterval(async () => {
      try {
        const updated = await getBooking(booking.id)
        setBooking(updated)
      } catch {
        // Keep polling; transient errors are fine while payment completes.
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [booking?.id, booking?.status])

  const handleBook = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const payload = {
        trip: tripId,
        phone_number: phone,
      }
      if (alightingStopId) payload.alighting_stop_id = alightingStopId
      const res = await createBooking(payload)
      const created = {
        id: res.data.booking_id,
        status: res.data.status,
        short_code: res.data.short_code ?? null,
        qr_code_token: res.data.qr_code_token ?? null,
      }

      if (created.status === 'confirmed') {
        const full = await getBooking(created.id)
        setBooking(full)
      } else {
        setBooking(created)
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Booking failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const alightingStopName =
    booking?.alighting_stop_name
    || stops?.find(s => s.id === alightingStopId)?.name
    || 'Final stop'

  if (loadingTrip) return (
    <div className="flex justify-center py-12">
      <svg className="animate-spin h-8 w-8 text-green-deep" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
    </div>
  )

  if (booking) return (
    <div className="flex flex-col gap-6">
      {booking.status === 'confirmed' || booking.status === 'boarded' ? (
        <>
          <div className="text-center">
            <div className="text-5xl mb-2">✅</div>
            <h2 className="text-xl font-bold text-green-deep">Booking Confirmed!</h2>
            <p className="text-ink-light text-sm mt-1">
              Payment received. Keep this ticket ready for boarding.
            </p>
          </div>

          <TicketDisplay
            shortCode={booking.short_code}
            qrCodeToken={booking.qr_code_token}
            status={booking.status}
            routeName={booking.trip_details?.route_name || trip?.route_name}
            departureTime={formatDateTime(booking.trip_details?.departure_time || trip?.departure_time)}
            alightingStop={alightingStopName}
            farePaid={booking.fare_paid ?? trip?.fare}
          />
        </>
      ) : (
        <>
          <div className="text-center">
            <h2 className="text-xl font-bold text-ink">Booking started</h2>
            <p className="text-ink-light text-sm mt-1">
              Complete M-Pesa payment to receive your boarding ticket.
            </p>
          </div>

          <TicketDisplay status={booking.status} />
        </>
      )}

      <div className="flex gap-3">
        <Button variant="secondary" className="flex-1" onClick={() => navigate('/commuter')}>
          Search more trips
        </Button>
        <Button className="flex-1" onClick={() => navigate('/commuter/tickets')}>
          View my tickets
        </Button>
      </div>
    </div>
  )

  return (
    <div className="flex flex-col gap-6">
      <button
        onClick={() => navigate('/commuter')}
        className="flex items-center gap-2 text-sm text-ink-light hover:text-ink transition-colors"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M19 12H5M12 5l-7 7 7 7"/>
        </svg>
        Back to trips
      </button>

      {trip && (
        <Card>
          <h2 className="font-bold text-lg text-ink mb-1" style={{fontFamily: 'serif'}}>
            {trip.route_name}
          </h2>
          <p className="text-ink-light text-sm mb-4">{formatDateTime(trip.departure_time)}</p>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-green-pale rounded-xl p-3">
              <p className="text-xs text-ink-light mb-0.5">Fare</p>
              <p className="font-bold text-green-deep">KES {Number(trip.fare).toLocaleString()}</p>
            </div>
            <div className="bg-green-pale rounded-xl p-3">
              <p className="text-xs text-ink-light mb-0.5">Seats available</p>
              <p className="font-bold text-green-deep">{trip.available_seats}</p>
            </div>
          </div>
        </Card>
      )}

      <Card>
        <h3 className="font-semibold text-ink mb-4">Book your seat</h3>
        <form onSubmit={handleBook} className="flex flex-col gap-4">

          {/* Alighting stop selector */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-ink">
              Where are you getting off?
            </label>
            {loadingStops ? (
              <div className="h-12 bg-gray-100 rounded-xl animate-pulse" />
            ) : (
              <div className="flex flex-col gap-2">
                {stops?.slice(1).map(stop => (
                  <button
                    key={stop.id}
                    type="button"
                    onClick={() => setAlightingStopId(stop.id)}
                    className={`flex items-center justify-between px-4 py-3 rounded-xl border-2 transition-all text-left ${
                      alightingStopId === stop.id
                        ? 'border-green-deep bg-green-pale'
                        : 'border-gray-200 bg-white hover:border-green-mid'
                    }`}
                  >
                    <span className="font-medium text-ink">{stop.name}</span>
                    {alightingStopId === stop.id && (
                      <svg className="w-5 h-5 text-green-deep" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    )}
                  </button>
                ))}
              </div>
            )}
            <p className="text-xs text-ink-light mt-1">
              Boarding from: {stops?.[0]?.name || 'Route origin'}
            </p>
          </div>

          <Input
            label="M-Pesa phone number"
            type="tel"
            placeholder="e.g. 0712 345 678"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            required
          />

          <p className="text-xs text-ink-light">
            You'll receive an M-Pesa prompt on this number. After payment you'll get a QR code and 6-digit boarding code for the conductor.
          </p>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
              {error}
            </div>
          )}

          <Button
            type="submit"
            loading={loading}
            disabled={!alightingStopId}
            className="w-full"
          >
            Pay KES {trip ? Number(trip.fare).toLocaleString() : '—'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
