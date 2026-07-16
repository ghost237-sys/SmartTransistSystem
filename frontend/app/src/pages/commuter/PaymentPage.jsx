import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getTrip } from '../../api/trips'
import { useAuth } from '../../auth/AuthContext'
import { createBooking, createMultiModeBooking } from '../../api/bookings'
import { PAYMENT_METHODS } from '../../constants/paymentMethods'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'

function PaymentMethodIcon({ method }) {
  const initials = method.name
    .split(/[\s/]+/)
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div
      className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0"
      style={{ backgroundColor: method.color }}
    >
      {initials}
    </div>
  )
}

export default function PaymentPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const { state: rideState } = useLocation()

  const { user } = useAuth()
  const [selectedMethod, setSelectedMethod] = useState('mpesa')
  const [phone, setPhone] = useState(user?.phoneNumber || '')
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState('')

  const pickupStopName = rideState?.pickupStopName
  const alightingStopName = rideState?.alightingStopName

  const { data: trip, isLoading } = useQuery({
    queryKey: ['trip', tripId],
    queryFn: async () => (await getTrip(tripId)).data,
  })

  const selected = PAYMENT_METHODS.find(m => m.id === selectedMethod)
  const needsPhone = selected?.type === 'mobile' || selectedMethod === 'mpesa'

  const handlePay = async () => {
    if (!phone && needsPhone) {
      setError('Enter your phone number to continue.')
      return
    }

    setError('')
    setProcessing(true)

    // Brief UX delay so payment feels real during demo
    await new Promise(r => setTimeout(r, 1500))

    try {
      let res
      if (rideState?.bookingData) {
        const payload = {
          ...rideState.bookingData,
          phone_number: phone || '0712345678',
          payment_method: selectedMethod,
          use_pass: false,
        }
        res = await createMultiModeBooking(payload)
      } else {
        const payload = {
          trip: tripId,
          phone_number: phone || '0712345678',
          payment_method: selectedMethod,
        }
        if (rideState?.pickupStopId) payload.boarding_stop_id = rideState.pickupStopId
        if (rideState?.alightingStopId) payload.alighting_stop_id = rideState.alightingStopId
        res = await createBooking(payload)
      }

      const bookingId = res.data.booking_id || res.data.outbound_booking_id

      navigate(`/commuter/booking/${bookingId}`, {
        replace: true,
        state: {
          pickupStopName: rideState?.pickupStopName,
          alightingStopName: rideState?.alightingStopName,
          etaMinutes: rideState?.etaMinutes,
          paymentMethod: selected?.name,
          isTwoWay: rideState?.isTwoWay,
          returnTime: rideState?.returnTime,
          isLinkedJourney: rideState?.isLinkedJourney,
          linkedRouteId: rideState?.linkedRouteId,
          firstLeg: rideState?.firstLeg,
          secondLeg: rideState?.secondLeg,
          transferStationName: rideState?.transferStationName,
        },
      })
    } catch (err) {
      setError(err.response?.data?.detail || 'Payment failed. Please try again.')
      setProcessing(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <svg className="animate-spin h-8 w-8 text-green-deep" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      </div>
    )
  }

  if (processing) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-6">
        <div className="relative">
          <div className="w-20 h-20 rounded-full border-4 border-green-pale border-t-green-deep animate-spin" />
          <div
            className="absolute inset-0 flex items-center justify-center text-white font-bold text-xs rounded-full m-3"
            style={{ backgroundColor: selected?.color }}
          >
            {selected?.name.split(' ')[0]}
          </div>
        </div>
        <div className="text-center">
          <h2 className="text-xl font-bold text-ink">Processing payment</h2>
          <p className="text-ink-light text-sm mt-2">
            Confirming KES {Number(rideState?.totalFare ?? trip?.fare ?? 0).toLocaleString()} via {selected?.name}…
          </p>
        </div>
      </div>
    )
  }

  const handleBack = () => {
    if (rideState?.bookingData) {
      navigate('/commuter')
    } else {
      navigate(`/commuter/book/${tripId}`, { state: rideState })
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <button
        onClick={handleBack}
        className="flex items-center gap-2 text-sm text-ink-light hover:text-ink transition-colors"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M19 12H5M12 5l-7 7 7 7"/>
        </svg>
        Back
      </button>

      <div>
        <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
          Choose payment method
        </h1>
        <p className="text-ink-light text-sm mt-1">
          Pay KES {Number(rideState?.totalFare ?? trip?.fare ?? 0).toLocaleString()} for your seat
        </p>
      </div>

      {trip && (
        <Card className="bg-green-pale/50 border-green-200">
          <p className="text-xs text-ink-light uppercase tracking-wide mb-1">Your trip</p>
          <p className="font-semibold text-ink">{trip.route_name}</p>
          <div className="mt-2 text-sm text-ink-light flex flex-col gap-0.5">
            {pickupStopName && <span>Board at: <strong className="text-ink">{pickupStopName}</strong></span>}
            {alightingStopName && <span>Alight at: <strong className="text-ink">{alightingStopName}</strong></span>}
          </div>
        </Card>
      )}

      <div>
        <p className="text-xs font-medium text-ink-light uppercase tracking-wide mb-3">
          Mobile money
        </p>
        <div className="flex flex-col gap-2">
          {PAYMENT_METHODS.filter(m => m.type === 'mobile').map(method => (
            <button
              key={method.id}
              type="button"
              onClick={() => setSelectedMethod(method.id)}
              className={`flex items-center gap-4 p-4 rounded-xl border-2 transition-all text-left ${
                selectedMethod === method.id
                  ? 'border-green-deep bg-green-pale/60 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-green-mid'
              }`}
            >
              <PaymentMethodIcon method={method} />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-ink">{method.name}</p>
                <p className="text-xs text-ink-light">{method.provider}</p>
              </div>
              {selectedMethod === method.id && (
                <svg className="w-5 h-5 text-green-deep shrink-0" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              )}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs font-medium text-ink-light uppercase tracking-wide mb-3">
          Banks
        </p>
        <div className="grid grid-cols-1 gap-2">
          {PAYMENT_METHODS.filter(m => m.type === 'bank').map(method => (
            <button
              key={method.id}
              type="button"
              onClick={() => setSelectedMethod(method.id)}
              className={`flex items-center gap-4 p-4 rounded-xl border-2 transition-all text-left ${
                selectedMethod === method.id
                  ? 'border-green-deep bg-green-pale/60 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-green-mid'
              }`}
            >
              <PaymentMethodIcon method={method} />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-ink">{method.name}</p>
                <p className="text-xs text-ink-light">{method.description}</p>
              </div>
              {selectedMethod === method.id && (
                <svg className="w-5 h-5 text-green-deep shrink-0" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              )}
            </button>
          ))}
        </div>
      </div>

      <Card>
        <Input
          label={needsPhone ? 'Phone number' : 'Phone number (optional)'}
          type="tel"
          placeholder="e.g. 0712 345 678"
          value={phone}
          onChange={e => setPhone(e.target.value)}
          required={needsPhone}
        />
        <p className="text-xs text-ink-light mt-2">
          {selected?.description}. Demo mode — no real charge is made.
        </p>
      </Card>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      <Button className="w-full py-4 text-base" onClick={handlePay}>
        Pay KES {trip ? Number(trip.fare).toLocaleString() : '—'} with {selected?.name}
      </Button>
    </div>
  )
}
