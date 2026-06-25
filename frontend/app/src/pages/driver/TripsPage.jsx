import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDriverTrips } from '../../api/trips'

function formatTime(datetime) {
  return new Date(datetime).toLocaleTimeString('en-KE', {
    hour: '2-digit', minute: '2-digit', hour12: true,
  })
}

function statusColor(status) {
  if (status === 'scheduled') return 'text-green-300'
  if (status === 'departed') return 'text-amber'
  return 'text-white/40'
}

export default function TripsPage() {
  const navigate = useNavigate()

  const { data: trips, isLoading } = useQuery({
    queryKey: ['driver-trips'],
    queryFn: async () => (await getDriverTrips()).data,
    refetchInterval: 30_000,
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <svg className="animate-spin h-8 w-8 text-amber" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold text-white" style={{ fontFamily: 'serif' }}>
          MY TRIPS
        </h1>
        <p className="text-white/50 text-sm mt-1">
          Select a trip to start sharing your live location with passengers.
        </p>
      </div>

      {!trips || trips.length === 0 ? (
        <div className="bg-black/20 rounded-2xl p-8 text-center border border-white/10">
          <div className="text-4xl mb-3">🚌</div>
          <p className="text-white/70 font-medium">No active trips assigned</p>
          <p className="text-white/40 text-sm mt-1">
            Check back when your fleet manager schedules your next run.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {trips.map(trip => (
            <button
              key={trip.id}
              onClick={() => navigate(`/driver/trip/${trip.id}`)}
              className="bg-black/20 hover:bg-black/30 border border-white/10 hover:border-amber/40 rounded-2xl px-5 py-4 text-left transition-all"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-white font-bold text-xl">{trip.route_name}</p>
                  <p className="text-white/50 text-sm mt-1">
                    {formatTime(trip.departure_time)} · {trip.vehicle_plate}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className={`text-sm font-bold uppercase ${statusColor(trip.status)}`}>
                    {trip.status}
                  </p>
                  <p className="text-amber text-xs mt-1 font-semibold">START GPS →</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
