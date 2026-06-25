import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { recordCashPayment } from '../../api/bookings'
import client from '../../api/client'
import Button from '../../components/ui/Button'

export default function CashPage() {
  const [selectedTrip, setSelectedTrip] = useState(null)
  const [amount, setAmount] = useState('')
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const { data: myTrips } = useQuery({
    queryKey: ['conductor-trips'],
    queryFn: async () => (await client.get('/api/routing/conductor/trips/')).data,
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await recordCashPayment({
        trip_id: selectedTrip.id,
        amount,
        commuter_phone: phone,
      })
      setResult(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record payment.')
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setResult(null)
    setError('')
    setAmount('')
    setPhone('')
  }

  if (result) return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold text-amber" style={{ fontFamily: 'serif' }}>CASH PAYMENT</h1>
      <div className="bg-green-500/20 border border-green-500/40 rounded-2xl p-8 text-center">
        <div className="text-5xl mb-4">💵</div>
        <p className="text-green-400 font-bold text-2xl mb-2">RECORDED</p>
        <p className="text-white/60 text-sm font-mono">{result.booking_id}</p>
        <Button className="mt-6 w-full" onClick={reset}>RECORD ANOTHER</Button>
      </div>
    </div>
  )

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold text-amber" style={{ fontFamily: 'serif' }}>CASH PAYMENT</h1>

      {/* Trip selector */}
      {!selectedTrip ? (
        <div className="flex flex-col gap-3">
          <p className="text-white/60 text-sm uppercase tracking-wider">Select trip</p>
          {!myTrips || myTrips.length === 0 ? (
            <div className="bg-white/5 rounded-2xl p-6 text-center">
              <p className="text-white/40">No active trips assigned to you.</p>
            </div>
          ) : (
            myTrips.map(trip => (
              <button
                key={trip.id}
                onClick={() => { setSelectedTrip(trip); setAmount(trip.fare) }}
                className="bg-white/5 hover:bg-white/10 border border-white/10 hover:border-amber/50 rounded-2xl px-5 py-4 text-left transition-all"
              >
                <p className="text-white font-bold text-lg">{trip.route_name}</p>
                <p className="text-white/50 text-sm">
                  Fare: KES {Number(trip.fare).toLocaleString()} · {trip.available_seats} seats left
                </p>
              </button>
            ))
          )}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="bg-white/5 rounded-xl px-4 py-3 flex items-center justify-between">
            <div>
              <p className="text-white font-bold">{selectedTrip.route_name}</p>
              <p className="text-white/50 text-sm">KES {Number(selectedTrip.fare).toLocaleString()}</p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedTrip(null)}
              className="text-white/40 hover:text-white text-sm transition-colors"
            >
              Change
            </button>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-white/60 text-sm font-bold uppercase tracking-wider">Amount (KES)</label>
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              required
              className="w-full px-4 py-4 rounded-xl bg-white/10 border border-white/20 text-white outline-none focus:border-amber text-2xl font-bold"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-white/60 text-sm font-bold uppercase tracking-wider">Phone (optional)</label>
            <input
              type="tel"
              placeholder="0712 345 678"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              className="w-full px-4 py-4 rounded-xl bg-white/10 border border-white/20 text-white placeholder-white/30 outline-none focus:border-amber text-lg"
            />
          </div>

          {error && (
            <div className="bg-red-500/20 border border-red-500/40 rounded-xl px-4 py-3">
              <p className="text-red-400 font-bold text-center">{error}</p>
            </div>
          )}

          <Button type="submit" loading={loading} className="w-full py-5 text-xl mt-2">
            RECORD CASH PAYMENT
          </Button>
        </form>
      )}
    </div>
  )
}