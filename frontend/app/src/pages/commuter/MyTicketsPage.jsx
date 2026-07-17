import { useQuery } from '@tanstack/react-query'
import { getMyBookings } from '../../api/bookings'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import TicketDisplay from '../../components/TicketDisplay'
import { useNavigate } from 'react-router-dom'
import Button from '../../components/ui/Button'

function statusVariant(status) {
  return {
    confirmed: 'green',
    held: 'amber',
    boarded: 'blue',
    cancelled: 'red',
    expired: 'gray',
  }[status] || 'gray'
}

function formatDateTime(datetime) {
  return new Date(datetime).toLocaleString('en-KE', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit', hour12: true
  })
}

export default function MyTicketsPage() {
  const navigate = useNavigate()

  const { data: bookings, isLoading } = useQuery({
    queryKey: ['my-bookings'],
    queryFn: getMyBookings,
  })

  if (isLoading) return (
    <div className="flex justify-center py-12">
      <svg className="animate-spin h-8 w-8 text-green-deep" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
    </div>
  )

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
        My Tickets
      </h1>

      {(!bookings || bookings.length === 0) && (
        <Card className="text-center py-12">
          <div className="text-4xl mb-3">🎫</div>
          <p className="text-ink font-medium mb-1">No tickets yet</p>
          <p className="text-ink-light text-sm mb-4">Book a trip to see your tickets here.</p>
          <Button onClick={() => navigate('/commuter')}>Find a trip</Button>
        </Card>
      )}

      <div className="flex flex-col gap-4">
        {bookings?.map(booking => {
          const hasBoardingTicket = booking.short_code && booking.qr_code_token

          return (
            <div key={booking.id} className="flex flex-col gap-3">
              <Card>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-ink">
                        {booking.trip_details?.route_name || 'Trip'}
                      </span>
                      <Badge variant={statusVariant(booking.status)}>{booking.status}</Badge>
                    </div>
                    {booking.trip_details?.departure_time && booking.status === 'boarded' && (
                      <p className="text-sm text-ink-light">
                        {formatDateTime(booking.trip_details.departure_time)}
                      </p>
                    )}
                    {booking.boarding_stop_name && (
                      <p className="text-sm text-ink-light mt-1">
                        Board at: {booking.boarding_stop_name}
                      </p>
                    )}
                    {booking.alighting_stop_name && (
                      <p className="text-sm text-ink-light mt-1">
                        Alighting: {booking.alighting_stop_name}
                      </p>
                    )}
                  </div>
                  {booking.status === 'confirmed' && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => navigate(`/booking/${booking.id}`)}
                    >
                      Track bus
                    </Button>
                  )}
                </div>
              </Card>

              {hasBoardingTicket ? (
                <TicketDisplay
                  compact
                  shortCode={booking.short_code}
                  qrCodeToken={booking.qr_code_token}
                  status={booking.status}
                  routeName={booking.trip_details?.route_name}
                  boardingStop={booking.boarding_stop_name}
                  alightingStop={booking.alighting_stop_name}
                  farePaid={booking.fare_paid}
                />
              ) : booking.status === 'held' ? (
                <TicketDisplay status={booking.status} />
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
