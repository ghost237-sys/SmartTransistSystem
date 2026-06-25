import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getTrips } from '../../api/trips'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'

function formatTime(datetime) {
  return new Date(datetime).toLocaleTimeString('en-KE', {
    hour: '2-digit', minute: '2-digit', hour12: true
  })
}

function formatDate(datetime) {
  return new Date(datetime).toLocaleDateString('en-KE', {
    weekday: 'short', day: 'numeric', month: 'short'
  })
}

function statusVariant(status) {
  return { scheduled: 'green', departed: 'amber', completed: 'gray', cancelled: 'red' }[status] || 'gray'
}

export default function TripSearchPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data: trips, isLoading, error } = useQuery({
    queryKey: ['trips'],
    queryFn: async () => {
      const res = await getTrips()
      return res.data
    },
  })

  const filtered = trips?.filter(trip =>
    !search || trip.route_name?.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
          Find a Trip
        </h1>
        <p className="text-ink-light text-sm mt-1">
          Book your seat and track your bus live.
        </p>
      </div>

      <div className="relative">
        <svg className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-light w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          type="text"
          placeholder="Search routes (e.g. Nairobi, Mombasa)"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-11 pr-4 py-3 rounded-xl border border-gray-200 bg-white text-ink placeholder-ink-light outline-none focus:border-green-mid focus:ring-2 focus:ring-green-pale transition-all"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <svg className="animate-spin h-8 w-8 text-green-deep" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
        </div>
      )}

      {error && (
        <Card className="border-red-100 bg-red-50">
          <p className="text-red-600 text-sm">Failed to load trips. Please try again.</p>
        </Card>
      )}

      {!isLoading && filtered.length === 0 && (
        <Card className="text-center py-12">
          <p className="text-ink-light">No trips found{search ? ` for "${search}"` : ''}.</p>
        </Card>
      )}

      <div className="flex flex-col gap-3">
        {filtered.map(trip => (
          <Card key={trip.id}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-ink truncate">{trip.route_name || 'Route'}</span>
                  <Badge variant={statusVariant(trip.status)}>{trip.status}</Badge>
                </div>
                <div className="text-sm text-ink-light">
                  {formatDate(trip.departure_time)} · {formatTime(trip.departure_time)}
                </div>
                <div className="mt-1">
                  <span className={`text-sm font-medium ${trip.available_seats > 0 ? 'text-green-mid' : 'text-red-500'}`}>
                    {trip.available_seats > 0 ? `${trip.available_seats} seats available` : 'Full'}
                  </span>
                </div>
              </div>

              <div className="flex flex-col items-end gap-2 shrink-0">
                <div className="text-lg font-bold text-ink">
                  KES {Number(trip.fare).toLocaleString()}
                </div>
                <div className="flex flex-row gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => navigate(`/commuter/track/${trip.id}`)}
                  >
                    Track
                  </Button>
                  <Button
                    size="sm"
                    disabled={trip.available_seats === 0 || trip.status !== 'scheduled'}
                    onClick={() => navigate(`/commuter/book/${trip.id}`)}
                  >
                    Book
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}