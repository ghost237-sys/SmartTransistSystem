import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getTrip, getTripStops } from '../../api/trips'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'

export default function BookingPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const { state: rideState } = useLocation()

  const [alightingStopId, setAlightingStopId] = useState(rideState?.alightingStopId || '')

  const pickupStopId = rideState?.pickupStopId
  const pickupStopName = rideState?.pickupStopName
  const etaMinutes = rideState?.etaMinutes

  const { data: trip, isLoading: loadingTrip } = useQuery({
    queryKey: ['trip', tripId],
    queryFn: async () => (await getTrip(tripId)).data,
  })

  const { data: stops, isLoading: loadingStops } = useQuery({
    queryKey: ['trip-stops', tripId],
    queryFn: async () => (await getTripStops(tripId)).data,
  })

  const alightingStopName =
    rideState?.alightingStopName
    || stops?.find(s => s.id === alightingStopId)?.name
    || 'Final stop'

  const boardingStopName = pickupStopName || stops?.[0]?.name || 'Route origin'

  const pickupSequence = stops?.find(s => s.id === pickupStopId)?.sequence
  const alightingStops = stops?.filter(s =>
    pickupSequence != null ? s.sequence > pickupSequence : s.sequence > 0
  ) ?? []

  const serviceLabel = etaMinutes
    ? `Active · ETA ${Math.round(etaMinutes)} min to ${boardingStopName}`
    : 'Active now'

  const handleContinue = () => {
    navigate(`/commuter/pay/${tripId}`, {
      state: {
        pickupStopId,
        pickupStopName,
        alightingStopId,
        alightingStopName,
        etaMinutes,
      },
    })
  }

  if (loadingTrip) {
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
      <button
        onClick={() => navigate('/commuter')}
        className="flex items-center gap-2 text-sm text-ink-light hover:text-ink transition-colors"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M19 12H5M12 5l-7 7 7 7"/>
        </svg>
        Back to search
      </button>

      {trip && (
        <Card>
          <h2 className="font-bold text-lg text-ink mb-1" style={{ fontFamily: 'serif' }}>
            {trip.route_name}
          </h2>
          <p className="text-green-mid text-sm font-medium mb-4">{serviceLabel}</p>
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
        <h3 className="font-semibold text-ink mb-4">Confirm your stops</h3>

        <div className="flex flex-col gap-3">
          <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3">
            <p className="text-xs text-ink-light uppercase tracking-wide">Board at</p>
            <p className="font-semibold text-ink text-lg">{boardingStopName}</p>
            {etaMinutes != null && (
              <p className="text-sm text-blue-700 mt-1">Bus ~{Math.round(etaMinutes)} min away</p>
            )}
          </div>

          {!rideState?.alightingStopId ? (
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-ink">Where are you getting off?</label>
              {loadingStops ? (
                <div className="h-12 bg-gray-100 rounded-xl animate-pulse" />
              ) : (
                <div className="flex flex-col gap-2 max-h-64 overflow-y-auto">
                  {alightingStops.map(stop => (
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
            </div>
          ) : (
            <div className="bg-green-pale rounded-xl px-4 py-3">
              <p className="text-xs text-ink-light uppercase tracking-wide">Alight at</p>
              <p className="font-semibold text-ink text-lg">{alightingStopName}</p>
            </div>
          )}
        </div>

        <Button
          className="w-full mt-6"
          disabled={!alightingStopId}
          onClick={handleContinue}
        >
          Continue to payment
        </Button>
      </Card>
    </div>
  )
}
