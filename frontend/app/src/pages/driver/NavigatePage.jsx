import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDriverTrip, getTripStops } from '../../api/trips'
import { postPosition } from '../../api/telemetry'
import MapView from '../../components/ui/MapView'
import Button from '../../components/ui/Button'

const POST_INTERVAL_MS = 3000

function formatTime(datetime) {
  return new Date(datetime).toLocaleTimeString('en-KE', {
    hour: '2-digit', minute: '2-digit', hour12: true,
  })
}

export default function NavigatePage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const watchIdRef = useRef(null)
  const positionRef = useRef(null)

  const [tracking, setTracking] = useState(false)
  const [position, setPosition] = useState(null)
  const [geoError, setGeoError] = useState(null)
  const [sendError, setSendError] = useState(null)
  const [lastSent, setLastSent] = useState(null)
  const [pingsSent, setPingsSent] = useState(0)
  const [sending, setSending] = useState(false)

  const { data: trip, isLoading: loadingTrip } = useQuery({
    queryKey: ['driver-trip', tripId],
    queryFn: async () => (await getDriverTrip(tripId)).data,
  })

  const { data: stops } = useQuery({
    queryKey: ['trip-stops', tripId],
    queryFn: async () => (await getTripStops(tripId)).data,
    enabled: !!tripId,
  })

  const canTrack = trip && ['scheduled', 'departed'].includes(trip.status)

  useEffect(() => {
    if (!tracking) {
      if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current)
        watchIdRef.current = null
      }
      return
    }

    if (!navigator.geolocation) {
      setGeoError('Geolocation is not supported on this device.')
      setTracking(false)
      return
    }

    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setGeoError(null)
        const next = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          speed_kmh: pos.coords.speed != null ? pos.coords.speed * 3.6 : null,
        }
        positionRef.current = next
        setPosition(next)
      },
      (err) => {
        setGeoError(err.message || 'Unable to access your location.')
        setTracking(false)
      },
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 15000 },
    )

    return () => {
      if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current)
        watchIdRef.current = null
      }
    }
  }, [tracking])

  useEffect(() => {
    if (!tracking || !trip) return

    const send = async () => {
      const pos = positionRef.current
      if (!pos) return

      setSending(true)
      try {
        await postPosition({
          vehicle_id: trip.vehicle,
          trip_id: trip.id,
          latitude: pos.latitude,
          longitude: pos.longitude,
          speed_kmh: pos.speed_kmh,
        })
        setSendError(null)
        setLastSent(new Date())
        setPingsSent(c => c + 1)
      } catch (err) {
        setSendError(
          err.response?.data?.detail || 'Failed to send position. Check your connection.',
        )
      } finally {
        setSending(false)
      }
    }

    send()
    const id = setInterval(send, POST_INTERVAL_MS)
    return () => clearInterval(id)
  }, [tracking, trip?.id, trip?.vehicle])

  const routePath = stops?.map(s => [s.longitude, s.latitude]) ?? []

  if (loadingTrip) {
    return (
      <div className="flex justify-center py-12">
        <svg className="animate-spin h-8 w-8 text-amber" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      </div>
    )
  }

  if (!trip) {
    return (
      <div className="bg-black/20 rounded-2xl p-8 text-center border border-white/10">
        <p className="text-white/70">Trip not found or not assigned to you.</p>
        <Button variant="secondary" className="mt-4" onClick={() => navigate('/driver')}>
          Back to trips
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/driver')}
          className="text-white/40 hover:text-white transition-colors text-lg"
        >
          ←
        </button>
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'serif' }}>
            {trip.route_name}
          </h1>
          <p className="text-white/50 text-sm">
            {formatTime(trip.departure_time)} · {trip.vehicle_plate}
          </p>
        </div>
      </div>

      <div className="bg-black/20 rounded-xl px-4 py-3 flex items-center justify-between border border-white/10">
        <div>
          <p className="text-white/50 text-xs uppercase tracking-wider">Trip status</p>
          <p className="text-white font-bold text-lg uppercase">{trip.status}</p>
        </div>
        <div className="text-right">
          <p className="text-white/50 text-xs uppercase tracking-wider">GPS</p>
          <p className={`font-bold text-lg ${tracking ? 'text-green-300' : 'text-white/40'}`}>
            {tracking ? 'LIVE' : 'OFF'}
          </p>
        </div>
      </div>

      {!canTrack && (
        <div className="bg-amber/10 border border-amber/30 rounded-xl px-4 py-3 text-amber text-sm">
          This trip is no longer active. GPS sharing is disabled.
        </div>
      )}

      {geoError && (
        <div className="bg-red-500/10 border border-red-400/30 rounded-xl px-4 py-3 text-red-200 text-sm">
          {geoError}
        </div>
      )}

      {sendError && (
        <div className="bg-red-500/10 border border-red-400/30 rounded-xl px-4 py-3 text-red-200 text-sm">
          {sendError}
        </div>
      )}

      <div className="rounded-xl overflow-hidden border border-white/10">
        <MapView
          stops={stops ?? []}
          vehiclePosition={position}
          routePath={routePath}
          height="280px"
        />
      </div>

      {position && (
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-black/20 rounded-xl p-3 text-center border border-white/10">
            <p className="text-white/50 text-xs">Speed</p>
            <p className="text-white font-bold">
              {position.speed_kmh != null ? `${Math.round(position.speed_kmh)} km/h` : '—'}
            </p>
          </div>
          <div className="bg-black/20 rounded-xl p-3 text-center border border-white/10">
            <p className="text-white/50 text-xs">Pings sent</p>
            <p className="text-white font-bold">{pingsSent}</p>
          </div>
          <div className="bg-black/20 rounded-xl p-3 text-center border border-white/10">
            <p className="text-white/50 text-xs">Last sent</p>
            <p className="text-white font-bold text-sm">
              {lastSent ? lastSent.toLocaleTimeString('en-KE') : '—'}
            </p>
          </div>
        </div>
      )}

      {canTrack && (
        tracking ? (
          <Button
            variant="danger"
            className="w-full py-4 text-lg"
            onClick={() => setTracking(false)}
            disabled={sending}
          >
            STOP SHARING LOCATION
          </Button>
        ) : (
          <Button
            className="w-full py-4 text-lg"
            onClick={() => setTracking(true)}
          >
            START SHARING LOCATION
          </Button>
        )
      )}

      {tracking && (
        <p className="text-white/40 text-xs text-center">
          Your position is broadcast to passengers every {POST_INTERVAL_MS / 1000} seconds.
          Keep this screen open while driving.
        </p>
      )}
    </div>
  )
}
