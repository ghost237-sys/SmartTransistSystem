import { useEffect, useRef, useState, useMemo } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getBooking, getBookingPickupStatus } from '../../api/bookings'
import { getTripStops } from '../../api/trips'
import { postPosition } from '../../api/telemetry'
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
  const [pollInterval, setPollInterval] = useState(false)

  // Simulation states
  const [activeSimLeg, setActiveSimLeg] = useState('leg1')
  const [isSimulating, setIsSimulating] = useState(false)
  const [simStep, setSimStep] = useState(0)
  const [simSpeed, setSimSpeed] = useState(2) // Default 2x speed

  const { data: booking, isLoading: loadingBooking } = useQuery({
    queryKey: ['booking', bookingId],
    queryFn: () => getBooking(bookingId),
    refetchInterval: pollInterval,
  })

  // Poll booking details if transfer is pending, so it confirms in real time
  useEffect(() => {
    if (booking?.linked_booking_details?.status === 'pending_transfer') {
      setPollInterval(3000)
    } else {
      setPollInterval(false)
    }
  }, [booking])

  const targetTripId = activeSimLeg === 'leg1'
    ? (booking?.trip_details?.id || booking?.trip)
    : booking?.linked_booking_details?.trip_details?.id

  const targetVehicleId = activeSimLeg === 'leg1'
    ? booking?.trip_details?.vehicle_id
    : booking?.linked_booking_details?.trip_details?.vehicle_id

  const tripId = booking?.trip_details?.id || booking?.trip

  const { data: pickupStatus, refetch: refetchEta } = useQuery({
    queryKey: ['pickup-status', bookingId],
    queryFn: () => getBookingPickupStatus(bookingId),
    enabled: !!bookingId && booking?.status === 'confirmed',
    refetchInterval: 15000,
  })

  const { data: stops } = useQuery({
    queryKey: ['trip-stops', targetTripId],
    queryFn: async () => (await getTripStops(targetTripId)).data,
    enabled: !!targetTripId,
  })

  // WebSocket connects to the active tracking trip (which switches when targetTripId switches)
  useEffect(() => {
    if (!targetTripId || booking?.status !== 'confirmed') return undefined

    const ws = new WebSocket(`${getWsBase()}/ws/trip/${targetTripId}/tracking/`)
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
  }, [targetTripId, booking?.status, refetchEta])

  // Generate interpolated coordinates between route stops
  const simPoints = useMemo(() => {
    if (!stops || stops.length === 0) return []
    const sortedStops = [...stops].sort((a, b) => a.sequence - b.sequence)
    const stepsPerLeg = 20
    const points = []

    for (let i = 0; i < sortedStops.length - 1; i++) {
      const start = sortedStops[i]
      const end = sortedStops[i + 1]
      for (let step = 0; step < stepsPerLeg; step++) {
        const pct = step / stepsPerLeg
        points.push({
          latitude: start.latitude + (end.latitude - start.latitude) * pct,
          longitude: start.longitude + (end.longitude - start.longitude) * pct,
          speed_kmh: 40 + Math.random() * 15,
          stopName: start.name,
        })
      }
    }

    const lastStop = sortedStops[sortedStops.length - 1]
    points.push({
      latitude: lastStop.latitude,
      longitude: lastStop.longitude,
      speed_kmh: 0,
      stopName: lastStop.name,
    })

    return points
  }, [stops])

  // Simulation execution loop
  useEffect(() => {
    if (!isSimulating || simPoints.length === 0) return undefined

    const intervalTime = 3000 / simSpeed

    const runStep = async () => {
      setSimStep(prevStep => {
        const nextStep = prevStep + 1
        if (nextStep >= simPoints.length) {
          setIsSimulating(false)
          return prevStep
        }

        const point = simPoints[nextStep]
        postPosition({
          vehicle_id: targetVehicleId,
          trip_id: targetTripId,
          latitude: point.latitude,
          longitude: point.longitude,
          speed_kmh: point.speed_kmh,
        }).catch(err => {
          console.error('Error posting simulated position:', err)
        })

        return nextStep
      })
    }

    const intervalId = setInterval(runStep, intervalTime)
    return () => clearInterval(intervalId)
  }, [isSimulating, simPoints, simSpeed, targetTripId, targetVehicleId])

  const startSim = () => {
    if (simStep < simPoints.length) {
      const point = simPoints[simStep]
      postPosition({
        vehicle_id: targetVehicleId,
        trip_id: targetTripId,
        latitude: point.latitude,
        longitude: point.longitude,
        speed_kmh: point.speed_kmh,
      }).catch(() => {})
    }
    setIsSimulating(true)
  }

  const stopSim = () => {
    setIsSimulating(false)
  }

  const resetSim = () => {
    setIsSimulating(false)
    setSimStep(0)
  }

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

      {/* Return Commute Alert Banner */}
      {(booking?.booking_type === 'return_outward' || pageState?.isTwoWay) && (
        <Card className="border-blue-200 bg-blue-50/40 p-4 flex gap-3 items-start">
          <span className="text-xl">📅</span>
          <div>
            <h4 className="font-bold text-blue-950 text-sm">Return Commute Booked</h4>
            <p className="text-xs text-blue-700 mt-1">
              Your return bus is scheduled and confirmed. It will be available at your return time ({pageState?.returnTime || 'the selected return time'}). We will notify you once it departs.
            </p>
          </div>
        </Card>
      )}

      {/* Transfer Journey Alert Banner */}
      {(booking?.booking_type === 'link_leg_1' || pageState?.isLinkedJourney) && (
        <Card className="border-purple-200 bg-purple-50/40 p-4 flex gap-3 items-start">
          <span className="text-xl">🔗</span>
          <div>
            <h4 className="font-bold text-purple-950 text-sm">Transfer Journey Booked</h4>
            <p className="text-xs text-purple-700 mt-1">
              Your transfer seat at <strong className="text-purple-900">{booking?.linked_booking_details?.boarding_stop_name || pageState?.transferStationName || 'the transfer hub'}</strong> is secured. The QR code activates automatically when your outbound bus approaches the station.
            </p>
          </div>
        </Card>
      )}

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



      {/* Tickets Display */}
      <div className="flex flex-col gap-4">
        {/* Main Ticket */}
        <div className="relative">
          {booking?.linked_booking_details && (
            <div className="absolute -top-3 left-4 bg-green-deep text-white text-[10px] uppercase font-bold px-2.5 py-0.5 rounded-full z-10">
              {booking.booking_type === 'link_leg_1' ? 'Leg 1: Outbound' : booking.booking_type === 'return_outward' ? 'Outbound Commute' : 'Outbound'}
            </div>
          )}
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
        </div>

        {/* Linked Ticket / Return Ticket / Leg 2 */}
        {booking?.linked_booking_details && (
          <div className="relative mt-2">
            <div className={`absolute -top-3 left-4 text-white text-[10px] uppercase font-bold px-2.5 py-0.5 rounded-full z-10 ${
              booking.booking_type.startsWith('link') ? 'bg-purple-600' : 'bg-blue-600'
            }`}>
              {booking.booking_type === 'link_leg_1' ? 'Leg 2: Transfer' : 'Return Commute'}
            </div>
            {booking.linked_booking_details.status === 'confirmed' ? (
              <TicketDisplay
                shortCode={booking.linked_booking_details.short_code}
                qrCodeToken={booking.linked_booking_details.qr_code_token}
                status={booking.linked_booking_details.status}
                routeName={booking.linked_booking_details.trip_details?.route_name}
                boardingStop={booking.linked_booking_details.boarding_stop_name}
                alightingStop={booking.linked_booking_details.alighting_stop_name}
                farePaid={booking.linked_booking_details.fare_paid}
              />
            ) : (
              <Card className="border-dashed border-2 border-purple-200 bg-purple-50/30 p-6 text-center">
                <div className="text-2xl mb-1">⏳</div>
                <h4 className="font-semibold text-purple-950 text-sm">Transfer Seat Held in Pending Bay</h4>
                <p className="text-xs text-purple-700 mt-1 max-w-md mx-auto">
                  Your seat on {booking.linked_booking_details.trip_details?.route_name} is reserved. The ticket QR code activates automatically when your current bus approaches the transfer station.
                </p>
                <div className="mt-3 flex items-center justify-center gap-1 text-[11px] text-purple-600 bg-white border border-purple-100 rounded-lg px-2.5 py-1 w-fit mx-auto">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-ping inline-block mr-1" />
                  Seat lock pending geofence breach (2.0 km threshold)
                </div>
              </Card>
            )}
          </div>
        )}
      </div>

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
