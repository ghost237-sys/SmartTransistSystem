import { useState } from 'react'
import { trackParcel } from '../../api/parcels'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'

function statusVariant(status) {
  return {
    registered: 'gray',
    loaded: 'amber',
    in_transit: 'amber',
    arrived: 'green',
    collected: 'blue',
  }[status] || 'gray'
}

function statusLabel(status) {
  return {
    registered: 'Registered — awaiting loading',
    loaded: 'Loaded onto vehicle',
    in_transit: 'In transit',
    arrived: 'Arrived at destination',
    collected: 'Collected',
  }[status] || status
}

export default function ParcelTrackingPage() {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [parcel, setParcel] = useState(null)
  const [error, setError] = useState('')

  const handleTrack = async (e) => {
    e.preventDefault()
    setError('')
    setParcel(null)
    setLoading(true)
    try {
      const data = await trackParcel(code.trim().toUpperCase())
      setParcel(data)
    } catch {
      setError('Parcel not found. Check your tracking code and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
          Track a Parcel
        </h1>
        <p className="text-ink-light text-sm mt-1">
          Enter your tracking code to see where your parcel is.
        </p>
      </div>

      {/* Search form */}
      <Card>
        <form onSubmit={handleTrack} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-ink">Tracking code</label>
            <input
              type="text"
              placeholder="e.g. KE-DEMO1"
              value={code}
              onChange={e => setCode(e.target.value.toUpperCase())}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white text-ink placeholder-ink-light outline-none focus:border-green-mid focus:ring-2 focus:ring-green-pale transition-all font-mono text-lg tracking-widest text-center uppercase"
              required
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
              {error}
            </div>
          )}

          <Button type="submit" loading={loading} className="w-full">
            Track Parcel
          </Button>
        </form>
      </Card>

      {/* Parcel result */}
      {parcel && (
        <div className="flex flex-col gap-4">
          {/* Status card */}
          <Card className={`${parcel.status === 'arrived' || parcel.status === 'collected'
            ? 'border-green-200 bg-green-50'
            : 'border-amber/30 bg-amber/5'}`}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="font-mono font-bold text-green-deep text-xl">
                  {parcel.tracking_code}
                </p>
                <p className="text-sm text-ink-light mt-0.5">
                  {parcel.description || 'No description'}
                </p>
              </div>
              <Badge variant={statusVariant(parcel.status)}>
                {parcel.status.replace('_', ' ').toUpperCase()}
              </Badge>
            </div>

            <div className="bg-white/60 rounded-xl px-4 py-3">
              <p className="text-sm font-medium text-ink">{statusLabel(parcel.status)}</p>
            </div>
          </Card>

          {/* Sender/Recipient */}
          <Card>
            <h3 className="font-semibold text-ink mb-3">Parcel Details</h3>
            <div className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between">
                <span className="text-ink-light">From</span>
                <span className="font-medium">{parcel.sender_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-light">To</span>
                <span className="font-medium">{parcel.recipient_name}</span>
              </div>
              {parcel.weight_kg && (
                <div className="flex justify-between">
                  <span className="text-ink-light">Weight</span>
                  <span className="font-medium">{parcel.weight_kg} kg</span>
                </div>
              )}
              {parcel.origin_stop_name && (
                <div className="flex justify-between">
                  <span className="text-ink-light">Origin</span>
                  <span className="font-medium">{parcel.origin_stop_name}</span>
                </div>
              )}
              {parcel.destination_stop_name && (
                <div className="flex justify-between">
                  <span className="text-ink-light">Destination</span>
                  <span className="font-medium">{parcel.destination_stop_name}</span>
                </div>
              )}
            </div>
          </Card>

          {/* Chain of custody timeline */}
          {parcel.scan_events?.length > 0 && (
            <Card>
              <h3 className="font-semibold text-ink mb-4">Journey Timeline</h3>
              <div className="flex flex-col gap-0">
                {parcel.scan_events.map((event, i) => (
                  <div key={event.id} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div className={`w-3 h-3 rounded-full mt-1 shrink-0 ${
                        i === parcel.scan_events.length - 1
                          ? 'bg-green-deep'
                          : 'bg-green-mid'
                      }`} />
                      {i < parcel.scan_events.length - 1 && (
                        <div className="w-0.5 flex-1 bg-green-pale my-1" />
                      )}
                    </div>
                    <div className="pb-4 flex-1">
                      <p className="text-sm font-semibold text-ink capitalize">
                        {event.event_type.replace('_', ' ')}
                      </p>
                      {event.vehicle && (
                        <p className="text-xs text-ink-light">
                          Vehicle: {event.vehicle}
                        </p>
                      )}
                      {event.notes && (
                        <p className="text-xs text-ink-light italic">{event.notes}</p>
                      )}
                      <p className="text-xs text-ink-light mt-0.5">
                        {new Date(event.scanned_at).toLocaleString('en-KE', {
                          day: 'numeric', month: 'short',
                          hour: '2-digit', minute: '2-digit', hour12: true
                        })}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {parcel.scan_events?.length === 0 && (
            <Card className="text-center py-6">
              <p className="text-ink-light text-sm">
                No scan events yet — your parcel has been registered but not yet loaded onto a vehicle.
              </p>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}