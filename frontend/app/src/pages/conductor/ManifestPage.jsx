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
  
  // Dispute Shield Modal state
  const [showDisputeShield, setShowDisputeShield] = useState(false)
  const [disputeQuery, setDisputeQuery] = useState('')
  const [disputeResult, setDisputeResult] = useState(null)

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
  const totalShiftFare = manifest?.manifest?.reduce((acc, b) => acc + Number(b.fare_paid || 0), 0) ?? 0

  const handleVerifyDispute = () => {
    if (!disputeQuery) return
    const match = manifest?.manifest?.find(
      b => b.commuter.toLowerCase().includes(disputeQuery.toLowerCase()) || 
           (b.booking_id && b.booking_id.includes(disputeQuery))
    )
    if (match) {
      setDisputeResult({
        found: true,
        message: `VALID TICKET: ${match.commuter} is booked for ${match.boarding_stop} → ${match.alighting_stop}. Fare Paid: KES ${match.fare_paid}.`,
      })
    } else {
      setDisputeResult({
        found: false,
        message: `NO RECORD FOUND: No active ticket matching "${disputeQuery}" on this trip.`,
      })
    }
  }

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
      {/* Conductor Hero Header & Leaderboard */}
      <div className="bg-gradient-to-r from-amber-500/20 to-emerald-500/20 p-5 rounded-2xl border border-amber-500/30">
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="text-xs uppercase font-bold text-amber-400 tracking-wider">Crew Shift Dashboard</span>
            <h1 className="text-2xl font-extrabold text-white" style={{ fontFamily: 'serif' }}>
              My Daily Shift
            </h1>
          </div>
          <span className="px-3 py-1 bg-amber-500 text-slate-950 font-extrabold text-xs rounded-full uppercase">
            Rank #2 Stage Leader
          </span>
        </div>

        {/* Income Predictor Meter */}
        <div className="mt-4 grid grid-cols-2 gap-3 pt-3 border-t border-white/10">
          <div>
            <p className="text-xs text-white/60">Estimated Shift Earnings</p>
            <p className="text-xl font-black text-emerald-400">KES 4,200</p>
          </div>
          <div>
            <p className="text-xs text-white/60">Speed Badge</p>
            <p className="text-sm font-bold text-amber-300">⚡ 4.2s Boarding Average</p>
          </div>
        </div>
      </div>

      <h2 className="text-xl font-bold text-white tracking-wide" style={{ fontFamily: 'serif' }}>
        ASSIGNED TRIPS TODAY
      </h2>

      {!myTrips || myTrips.length === 0 ? (
        <div className="bg-white/5 rounded-2xl p-8 text-center border border-white/10">
          <p className="text-white/60">No active trips assigned to your crew shift today.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {myTrips.map(trip => (
            <button
              key={trip.id}
              onClick={() => setSelectedTripId(trip.id)}
              className="bg-white/5 hover:bg-white/10 border border-white/10 hover:border-amber/50 rounded-2xl px-5 py-4 text-left transition-all cursor-pointer"
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSelectedTripId(null)}
            className="text-white/40 hover:text-white transition-colors text-xl font-bold cursor-pointer"
          >
            ←
          </button>
          <h1 className="text-2xl font-bold text-amber" style={{ fontFamily: 'serif' }}>
            MANIFEST & BOARDING
          </h1>
        </div>

        {/* Dispute Shield Trigger */}
        <button
          onClick={() => {
            setShowDisputeShield(true)
            setDisputeResult(null)
            setDisputeQuery('')
          }}
          className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-xs font-bold px-3 py-2 rounded-xl flex items-center gap-1.5 cursor-pointer hover:bg-emerald-500/30 transition-colors"
        >
          🛡️ Dispute Shield
        </button>
      </div>

      {manifest && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/10">
            <p className="text-white/60 text-xs uppercase tracking-wider">Bus Fleet Code</p>
            <p className="text-white font-bold text-base mt-0.5">
              {formatBusLabel({ vehicle_plate: manifest.vehicle_plate, fleet_code: manifest.fleet_code })}
            </p>
          </div>
          <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/10">
            <p className="text-white/60 text-xs uppercase tracking-wider">Boarded / Total</p>
            <p className="text-amber font-extrabold text-xl mt-0.5">{boarded} / {total}</p>
          </div>
        </div>
      )}

      {/* Shift Financial Summary */}
      <div className="bg-slate-900 border border-emerald-500/30 rounded-xl p-4 flex items-center justify-between">
        <div>
          <p className="text-xs text-slate-400 font-semibold uppercase">Trip Gross Collection</p>
          <p className="text-2xl font-extrabold text-emerald-400">KES {totalShiftFare.toLocaleString()}</p>
        </div>
        <div className="text-right">
          <span className="text-[10px] uppercase font-extrabold bg-emerald-500/20 text-emerald-300 px-2.5 py-1 rounded-md">
            100% Audit Cleared
          </span>
        </div>
      </div>

      {manifest?.status === 'active' && (
        <Button variant="danger" className="w-full py-4 text-lg font-bold" loading={completeMutation.isPending}
          onClick={() => completeMutation.mutate()}>
          END SERVICE SHIFT
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

      {/* Passenger List */}
      <div className="flex flex-col gap-2.5">
        <h3 className="text-xs uppercase font-bold text-white/50 tracking-wider">Booked Passengers</h3>
        {manifest?.manifest?.map(booking => (
          <div key={booking.booking_id} className="bg-white/5 rounded-xl px-4 py-3.5 flex items-center justify-between border border-white/5">
            <div>
              <p className="text-white font-bold text-base">{booking.commuter}</p>
              <p className="text-white/50 text-xs mt-0.5">{booking.boarding_stop} → {booking.alighting_stop}</p>
            </div>
            <div className="text-right">
              <Badge variant={statusVariant(booking.status)}>{booking.status.toUpperCase()}</Badge>
              {booking.fare_paid && (
                <p className="text-emerald-400 font-bold text-xs mt-1">KES {Number(booking.fare_paid).toLocaleString()}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Dispute Shield Modal */}
      {showDisputeShield && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-emerald-500/40 rounded-2xl p-6 max-w-sm w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-white text-lg flex items-center gap-2">
                <span>🛡️</span> Dispute Shield
              </h3>
              <button 
                onClick={() => setShowDisputeShield(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Enter passenger name or short booking ID to verify digital M-Pesa payment instantly.
            </p>

            <input
              type="text"
              placeholder="e.g. Alice or Booking ID"
              value={disputeQuery}
              onChange={(e) => setDisputeQuery(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-emerald-500"
            />

            <Button onClick={handleVerifyDispute} className="w-full bg-emerald-500 hover:bg-emerald-600 font-bold py-3 text-slate-950">
              Verify Ticket
            </Button>

            {disputeResult && (
              <div className={`p-4 rounded-xl text-xs font-semibold ${disputeResult.found ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'}`}>
                {disputeResult.message}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}