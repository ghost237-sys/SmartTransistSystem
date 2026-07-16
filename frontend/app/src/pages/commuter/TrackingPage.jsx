import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getTrip, getTripStops } from '../../api/trips'
import { getWsBase } from '../../api/client'
import MapView from '../../components/ui/MapView'
import Card from '../../components/ui/Card'

function formatTime(datetime) {
  return new Date(datetime).toLocaleTimeString('en-KE', {
    hour: '2-digit', minute: '2-digit', hour12: true
  })
}

export default function TrackingPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const wsRef = useRef(null)
  const [position, setPosition] = useState(null)
  const [connected, setConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)

  const { data: trip } = useQuery({
    queryKey: ['trip', tripId],
    queryFn: async () => (await getTrip(tripId)).data,
  })

  const { data: stops } = useQuery({
    queryKey: ['trip-stops', tripId],
    queryFn: async () => (await getTripStops(tripId)).data,
  })

  useEffect(() => {
    const ws = new WebSocket(`${getWsBase()}/ws/trip/${tripId}/tracking/`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setPosition(data)
        setLastUpdate(new Date())
      } catch {}
    }

    return () => ws.close()
  }, [tripId])

  // Build route path from stops for the map
  const routePath = stops?.map(s => [s.longitude, s.latitude]) ?? []

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
        <div>
          <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
            {trip.route_name}
          </h1>
          <p className="text-ink-light text-sm mt-1">
            Departing {formatTime(trip.departure_time)}
          </p>
        </div>
      )}

      {/* Connection status */}
      <Card className={connected ? 'border-green-200' : 'border-amber/30'}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-amber'}`} />
            <span className="text-sm font-medium text-ink">
              {connected ? 'Live tracking active' : 'Connecting...'}
            </span>
          </div>
          {lastUpdate && (
            <span className="text-xs text-ink-light">
              Updated {lastUpdate.toLocaleTimeString('en-KE')}
            </span>
          )}
        </div>
      </Card>

      {/* Real map */}
      <Card className="p-0 overflow-hidden">
        <MapView
          stops={stops ?? []}
          vehiclePosition={position}
          routePath={routePath}
          height="380px"
        />
        <div className="px-4 py-3 flex items-center gap-4 text-xs text-ink-light border-t border-gray-100">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-green-400 inline-block" />
            Origin
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-green-deep inline-block" />
            Stop
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-amber inline-block" />
            Destination
          </span>
          <span className="flex items-center gap-1.5">
            🚌 Live bus
          </span>
        </div>
      </Card>

      {/* Speed/position info */}
      {position && (
        <Card>
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-green-pale rounded-xl p-3 text-center">
              <p className="text-xs text-ink-light mb-0.5">Speed</p>
              <p className="font-bold text-green-deep">
                {position.speed_kmh ? `${Number(position.speed_kmh).toFixed(0)} km/h` : '—'}
              </p>
            </div>
            <div className="bg-green-pale rounded-xl p-3 text-center">
              <p className="text-xs text-ink-light mb-0.5">Vehicle</p>
              <p className="font-bold text-green-deep text-sm">{trip?.vehicle_plate || '—'}</p>
            </div>
            <div className="bg-green-pale rounded-xl p-3 text-center">
              <p className="text-xs text-ink-light mb-0.5">Route</p>
              <p className="font-bold text-green-deep text-sm">{trip?.route_name || '—'}</p>
            </div>
          </div>
        </Card>
      )}

      {!position && (
        <Card className="text-center py-8">
          <div className="text-4xl mb-3">🚌</div>
          <p className="text-ink font-medium mb-1">Waiting for bus location</p>
          <p className="text-ink-light text-sm">
            {connected
              ? 'Connected — waiting for the driver to send their position.'
              : 'Attempting to connect to live tracking...'}
          </p>
        </Card>
      )}
    </div>
  )
}