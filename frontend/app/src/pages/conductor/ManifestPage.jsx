import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getTripManifest, completeTrip } from '../../api/bookings'
import client from '../../api/client'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import { formatBusLabel } from '../../utils/busLabel'

function statusVariant(status) {
  return {
    confirmed: 'green', boarded: 'blue',
    held: 'amber', cancelled: 'red', expired: 'gray',
  }[status] || 'gray'
}

export default function ManifestPage() {
  const queryClient = useQueryClient()
  const [selectedTripId, setSelectedTripId] = useState(null)

  // Auto-load conductor's assigned trips
  const { data: myTrips, isLoading: loadingTrips } = useQuery({
    queryKey: ['conductor-trips'],
    queryFn: async () => {
      const res = await client.get('/api/routing/conductor/trips/')
      return res.data
    },
  })

  const { data: manifest, isLoading: loadingManifest } = useQuery({
    queryKey: ['manifest', selectedTripId],
    queryFn: async () => (await getTripManifest(selectedTripId)),
    enabled: !!selectedTripId,
    refetchInterval: 5000,
  })

  const completeMutation = useMutation({
    mutationFn: () => completeTrip(selectedTripId),
    onSuccess: () => queryClient.invalidateQueries(['manifest', selectedTripId]),
  })

  const boarded = manifest?.manifest?.filter(b => b.status === 'boarded').length ?? 0
  const confirmed = manifest?.manifest?.filter(b => b.status === 'confirmed').length ?? 0
  const total = manifest?.manifest?.length ?? 0

  if (loadingTrips) return (
    <div className="flex justify-center py-12">
      <svg className="animate-spin h-8 w-8 text-amber" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
    </div>
  )

  if (!selectedTripId) return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold text-amber" style={{ fontFamily: 'serif' }}>
        MY TRIPS
      </h1>

      {!myTrips || myTrips.length === 0 ? (
        <div className="bg-white/5 rounded-2xl p-8 text-center">
          <p className="text-white/60">No trips assigned to you today.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {myTrips.map(trip => (
            <button
              key={trip.id}
              onClick={() => setSelectedTripId(trip.id)}
              className="bg-white/5 hover:bg-white/10 border border-white/10 hover:border-amber/50 rounded-2xl px-5 py-4 text-left transition-all"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white font-bold text-xl">{trip.route_name}</p>
                  <p className="text-white/50 text-sm mt-1">
                    {formatBusLabel({ vehicle_plate: trip.vehicle_plate, fleet_code: trip.fleet_code })}
                  </p>
                  <p className="text-white/40 text-xs mt-1">
                    {trip.status === 'active' ? 'Active service' : trip.status}
                  </p>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-bold uppercase ${
                    trip.status === 'active' ? 'text-green-400' :
                    trip.status === 'completed' ? 'text-white/40' : 'text-amber'
                  }`}>{trip.status}</p>
                  <p className="text-white/40 text-xs mt-1">{trip.available_seats} seats left</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSelectedTripId(null)}
          className="text-white/40 hover:text-white transition-colors"
        >
          ←
        </button>
        <h1 className="text-3xl font-bold text-amber" style={{ fontFamily: 'serif' }}>
          MANIFEST
        </h1>
      </div>

      {manifest && (
        <>
          <div className="flex items-center justify-between bg-white/5 rounded-xl px-4 py-3">
            <div>
              <p className="text-white/60 text-xs uppercase tracking-wider">Bus</p>
              <p className="text-white font-bold">
                {formatBusLabel({ vehicle_plate: manifest.vehicle_plate, fleet_code: manifest.fleet_code })}
              </p>
            </div>
            <div className="text-right">
              <p className="text-white/60 text-xs uppercase tracking-wider">Confirmed / Boarded</p>
              <p className="text-amber font-bold text-2xl">{confirmed} / {boarded}</p>
            </div>
          </div>
        </>
      )}

      {manifest && (
        <div className="flex items-center justify-between bg-white/5 rounded-xl px-4 py-3">
          <div>
            <p className="text-white/60 text-xs uppercase tracking-wider">Status</p>
            <p className="text-white font-bold text-lg uppercase">{manifest.status}</p>
          </div>
          <div className="text-right">
            <p className="text-white/60 text-xs uppercase tracking-wider">Total passengers</p>
            <p className="text-amber font-bold text-2xl">{total}</p>
          </div>
        </div>
      )}

      {manifest?.status === 'active' && (
        <Button variant="danger" className="w-full py-4 text-lg" loading={completeMutation.isPending}
          onClick={() => completeMutation.mutate()}>
          END SERVICE
        </Button>
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
          <div key={booking.booking_id} className="bg-white/5 rounded-xl px-4 py-3 flex items-center justify-between">
            <div>
              <p className="text-white font-bold text-lg">{booking.commuter}</p>
              <p className="text-white/50 text-sm">{booking.boarding_stop} → {booking.alighting_stop}</p>
            </div>
            <div className="text-right">
              <Badge variant={statusVariant(booking.status)}>{booking.status.toUpperCase()}</Badge>
              {booking.fare_paid && (
                <p className="text-white/50 text-xs mt-1">KES {Number(booking.fare_paid).toLocaleString()}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}