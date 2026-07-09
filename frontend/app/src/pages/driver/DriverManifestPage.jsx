import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getTripManifest } from '../../api/bookings'
import client from '../../api/client'
import Badge from '../../components/ui/Badge'
import { formatBusLabel } from '../../utils/busLabel'

function statusVariant(status) {
  return {
    confirmed: 'green', boarded: 'blue',
    held: 'amber', cancelled: 'red', expired: 'gray',
  }[status] || 'gray'
}

export default function DriverManifestPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const [selectedTripId, setSelectedTripId] = useState(tripId || null)

  const { data: myTrips, isLoading: loadingTrips } = useQuery({
    queryKey: ['driver-trips'],
    queryFn: async () => (await client.get('/api/routing/driver/trips/')).data,
  })

  const { data: manifest, isLoading: loadingManifest } = useQuery({
    queryKey: ['manifest', selectedTripId],
    queryFn: async () => getTripManifest(selectedTripId),
    enabled: !!selectedTripId,
    refetchInterval: 5000,
  })

  const boarded = manifest?.manifest?.filter(b => b.status === 'boarded').length ?? 0
  const confirmed = manifest?.manifest?.filter(b => b.status === 'confirmed').length ?? 0
  const total = manifest?.manifest?.length ?? 0

  if (loadingTrips) {
    return (
      <div className="flex justify-center py-12">
        <svg className="animate-spin h-8 w-8 text-amber" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      </div>
    )
  }

  if (!selectedTripId) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-3xl font-bold text-white" style={{ fontFamily: 'serif' }}>PASSENGERS</h1>
        {!myTrips?.length ? (
          <div className="bg-black/20 rounded-2xl p-8 text-center border border-white/10">
            <p className="text-white/60">No active trips assigned.</p>
          </div>
        ) : (
          myTrips.map(trip => (
            <button
              key={trip.id}
              onClick={() => setSelectedTripId(trip.id)}
              className="bg-black/20 hover:bg-black/30 border border-white/10 rounded-2xl px-5 py-4 text-left"
            >
              <p className="text-white font-bold text-xl">{trip.route_name}</p>
              <p className="text-white/50 text-sm mt-1">
                {formatBusLabel({ vehicle_plate: trip.vehicle_plate, fleet_code: trip.fleet_code })}
              </p>
            </button>
          ))
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => setSelectedTripId(null)} className="text-white/40 hover:text-white">←</button>
        <h1 className="text-3xl font-bold text-white" style={{ fontFamily: 'serif' }}>MANIFEST</h1>
      </div>

      {manifest && (
        <>
          <div className="bg-black/20 rounded-xl px-4 py-3 border border-white/10">
            <p className="text-white font-bold">{manifest.route_name}</p>
            <p className="text-white/50 text-sm">
              {formatBusLabel({ vehicle_plate: manifest.vehicle_plate, fleet_code: manifest.fleet_code })}
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-black/20 rounded-xl p-3 border border-white/10">
              <p className="text-xs text-white/50">Confirmed</p>
              <p className="text-amber font-bold text-xl">{confirmed}</p>
            </div>
            <div className="bg-black/20 rounded-xl p-3 border border-white/10">
              <p className="text-xs text-white/50">Boarded</p>
              <p className="text-green-400 font-bold text-xl">{boarded}</p>
            </div>
            <div className="bg-black/20 rounded-xl p-3 border border-white/10">
              <p className="text-xs text-white/50">Total</p>
              <p className="text-white font-bold text-xl">{total}</p>
            </div>
          </div>
        </>
      )}

      {loadingManifest && (
        <div className="flex justify-center py-8">
          <svg className="animate-spin h-8 w-8 text-amber" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {manifest?.manifest?.map(booking => (
          <div key={booking.booking_id} className="bg-black/20 rounded-xl px-4 py-3 border border-white/10 flex justify-between">
            <div>
              <p className="text-white font-bold">{booking.commuter}</p>
              <p className="text-white/50 text-sm">{booking.boarding_stop} → {booking.alighting_stop}</p>
            </div>
            <Badge variant={statusVariant(booking.status)}>{booking.status.toUpperCase()}</Badge>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={() => navigate(`/driver/trip/${selectedTripId}`)}
        className="text-amber text-sm font-medium text-left"
      >
        Start GPS tracking →
      </button>
    </div>
  )
}
