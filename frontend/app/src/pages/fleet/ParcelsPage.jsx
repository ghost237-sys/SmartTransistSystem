import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getParcels, trackParcel } from '../../api/parcels'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'

function statusVariant(status) {
  return {
    registered: 'gray',
    loaded: 'amber',
    in_transit: 'amber',
    arrived: 'green',
    collected: 'blue',
  }[status] || 'gray'
}

export default function ParcelsPage() {
  const [trackCode, setTrackCode] = useState('')
  const [tracked, setTracked] = useState(null)
  const [trackError, setTrackError] = useState('')
  const [tracking, setTracking] = useState(false)

  const { data: parcels, isLoading } = useQuery({
    queryKey: ['parcels'],
    queryFn: async () => (await getParcels()),
  })

  const handleTrack = async (e) => {
    e.preventDefault()
    setTrackError('')
    setTracking(true)
    try {
      const res = await trackParcel(trackCode.trim().toUpperCase())
      setTracked(res.data)
    } catch {
      setTrackError('Parcel not found. Check the tracking code and try again.')
      setTracked(null)
    } finally {
      setTracking(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold text-ink" style={{ fontFamily: 'serif' }}>Parcels</h1>
        <p className="text-ink-light mt-1">Terminal-to-terminal parcel tracking</p>
      </div>

      {/* Track a parcel */}
      <Card>
        <h3 className="font-semibold text-ink mb-4">Track a Parcel</h3>
        <form onSubmit={handleTrack} className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Enter tracking code (e.g. KE-NNWJF9)"
              value={trackCode}
              onChange={e => setTrackCode(e.target.value)}
            />
          </div>
          <Button type="submit" loading={tracking}>Track</Button>
        </form>

        {trackError && (
          <p className="text-red-500 text-sm mt-2">{trackError}</p>
        )}

        {tracked && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="font-mono font-bold text-green-deep text-lg">{tracked.tracking_code}</p>
                <p className="text-sm text-ink-light">{tracked.sender_name} → {tracked.recipient_name}</p>
              </div>
              <Badge variant={statusVariant(tracked.status)}>{tracked.status.replace('_', ' ')}</Badge>
            </div>

            {/* Scan events timeline */}
            {tracked.scan_events?.length > 0 && (
              <div className="flex flex-col gap-2 mt-3">
                <p className="text-xs font-semibold text-ink-light uppercase tracking-wider">Chain of custody</p>
                {tracked.scan_events.map((event, i) => (
                  <div key={event.id} className="flex items-start gap-3">
                    <div className="flex flex-col items-center">
                      <div className="w-2.5 h-2.5 rounded-full bg-green-deep mt-1" />
                      {i < tracked.scan_events.length - 1 && (
                        <div className="w-0.5 h-6 bg-green-pale mt-1" />
                      )}
                    </div>
                    <div className="flex-1 pb-2">
                      <p className="text-sm font-medium text-ink capitalize">{event.event_type}</p>
                      <p className="text-xs text-ink-light">
                        {event.scanned_by} · {new Date(event.scanned_at).toLocaleString('en-KE')}
                      </p>
                      {event.notes && <p className="text-xs text-ink-light italic">{event.notes}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Card>

      {/* All parcels */}
      <div>
        <h2 className="text-lg font-semibold text-ink mb-3">All Parcels</h2>
        {isLoading && (
          <div className="flex justify-center py-8">
            <svg className="animate-spin h-6 w-6 text-green-deep" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
          </div>
        )}

        {!isLoading && (!parcels || parcels.length === 0) && (
          <Card className="text-center py-8">
            <p className="text-ink-light text-sm">No parcels registered yet.</p>
          </Card>
        )}

        <div className="flex flex-col gap-3">
          {parcels?.map(parcel => (
            <Card key={parcel.id}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono font-bold text-green-deep">{parcel.tracking_code}</span>
                    <Badge variant={statusVariant(parcel.status)}>{parcel.status.replace('_', ' ')}</Badge>
                  </div>
                  <p className="text-sm text-ink">{parcel.sender_name} → {parcel.recipient_name}</p>
                  <p className="text-xs text-ink-light mt-0.5">{parcel.description || 'No description'}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-semibold text-ink text-sm">KES {Number(parcel.fee).toLocaleString()}</p>
                  {parcel.weight_kg && (
                    <p className="text-xs text-ink-light">{parcel.weight_kg} kg</p>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}