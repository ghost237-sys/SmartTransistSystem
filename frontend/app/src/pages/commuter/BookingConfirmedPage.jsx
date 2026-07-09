import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getBooking, getBookingPickupStatus } from '../../api/bookings'
import { getTripStops } from '../../api/trips'
import { formatBusLabel } from '../../utils/busLabel'
import MapView from '../../components/ui/MapView'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import TicketDisplay from '../../components/TicketDisplay'

function getWsBase() {
  const api = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : 'http://localhost:8000')
  return api.replace(/^http/, 'ws')
}

export default function BookingConfirmedPage() {
  const { bookingId } = useParams()
  const navigate = useNavigate()
  const { state: pageState } = useLocation()
  const wsRef = useRef(null)
  const [livePosition, setLivePosition] = useState(null)

  const { data: booking, isLoading: loadingBooking } = useQuery({
    queryKey: ['booking', bookingId],
    queryFn: () => getBooking(bookingId),
  })

  const tripId = booking?.trip_details?.id || booking?.trip

  const { data: pickupStatus, refetch: refetchEta } = useQuery({
    queryKey: ['pickup-status', bookingId],
    queryFn: () => getBookingPickupStatus(bookingId),
    enabled: !!bookingId && booking?.status === 'confirmed',
    refetchInterval: 15000,
  })

  const { data: stops } = useQuery({
    queryKey: ['trip-stops', tripId],
    queryFn: async () => (await getTripStops(tripId)).data,
    enabled: !!tripId,
  })

  useEffect(() => {
    if (!tripId || booking?.status !== 'confirmed') return undefined

    const ws = new WebSocket(`${getWsBase()}/ws/trip/${tripId}/tracking/`)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setLivePosition(data)
        refetchEta()
      } catch {
        // ignore malformed frames
      }
    }

    return () => ws.close()
  }, [tripId, booking?.status, refetchEta])

  const vehiclePosition = livePosition || (pickupStatus?.vehicle_latitude ? {
    latitude: pickupStatus.vehicle_latitude,
    longitude: pickupStatus.vehicle_longitude,
    speed_kmh: pickupStatus.speed_kmh,
  } : null)

  const etaMinutes = pickupStatus?.eta_minutes ?? pageState?.etaMinutes
  const boardingStopName = booking?.boarding_stop_name || pageState?.pickupStopName
  const alightingStopName = booking?.alighting_stop_name || pageState?.alightingStopName
  const busLabel = formatBusLabel({
    vehicle_plate: pickupStatus?.vehicle_plate || booking?.trip_details?.vehicle_plate,
    fleet_code: pickupStatus?.fleet_code || booking?.trip_details?.fleet_code,
  })

  const pickupStop = stops?.find(s => String(s.id) === String(pickupStatus?.pickup_stop_id))
    || stops?.find(s => s.name === boardingStopName)

  const routePath = stops?.map(s => [s.longitude, s.latitude]) ?? []

  if (loadingBooking) {
    return (
      <div className="flex justify-center py-12">
        <svg className="animate-spin h-8 w-8 text-green-deep" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="text-center">
        <div className="text-5xl mb-2">✅</div>
        <h1 className="text-2xl font-bold text-green-deep" style={{ fontFamily: 'serif' }}>
          Payment confirmed
        </h1>
        {pageState?.paymentMethod && (
          <p className="text-ink-light text-sm mt-1">
            Paid via {pageState.paymentMethod}
          </p>
        )}
      </div>

      {/* ETA hero */}
      <Card className="text-center py-8 bg-gradient-to-b from-green-pale to-white border-green-200">
        <p className="text-xs font-medium text-ink-light uppercase tracking-widest mb-2">
          Bus arriving at your stage
        </p>
        {etaMinutes != null ? (
          <>
            <p className="text-6xl font-bold text-green-deep tabular-nums">
              {Math.max(1, Math.round(etaMinutes))}
            </p>
            <p className="text-lg text-ink-light mt-1">minutes</p>
          </>
        ) : (
          <p className="text-xl font-semibold text-ink">Calculating ETA…</p>
        )}
        <div className="mt-4 flex flex-col gap-1 text-sm">
          {busLabel && busLabel !== 'Bus' && (
            <p className="text-ink">
              Bus <span className="font-bold">{busLabel}</span>
            </p>
          )}
          {boardingStopName && (
            <p className="text-ink-light">
              Head to <span className="font-medium text-ink">{boardingStopName}</span>
            </p>
          )}
          {pickupStatus?.distance_km != null && (
            <p className="text-ink-light text-xs">
              {pickupStatus.distance_km} km away ·{' '}
              {pickupStatus.speed_kmh ? `${Math.round(pickupStatus.speed_kmh)} km/h` : 'live tracking'}
            </p>
          )}
        </div>
      </Card>

      {/* Live map */}
      <Card className="p-0 overflow-hidden">
        <MapView
          stops={stops ?? []}
          pickupStop={pickupStop}
          vehiclePosition={vehiclePosition}
          routePath={routePath}
          height="320px"
        />
        <div className="px-4 py-3 flex flex-wrap items-center gap-3 text-xs text-ink-light border-t border-gray-100">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-blue-500 inline-block border-2 border-blue-200" />
            Your pickup
          </span>
          <span className="flex items-center gap-1.5">🚌 Live bus</span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-green-deep inline-block" />
            Route stops
          </span>
        </div>
      </Card>

      {booking?.status === 'confirmed' && (
        <TicketDisplay
          shortCode={booking.short_code}
          qrCodeToken={booking.qr_code_token}
          status={booking.status}
          routeName={booking.trip_details?.route_name}
          boardingStop={boardingStopName}
          alightingStop={alightingStopName}
          farePaid={booking.fare_paid}
        />
      )}

      <div className="flex gap-3">
        <Button variant="secondary" className="flex-1" onClick={() => navigate('/commuter')}>
          Find another ride
        </Button>
        <Button className="flex-1" onClick={() => navigate('/commuter/tickets')}>
          My tickets
        </Button>
      </div>
    </div>
  )
}
