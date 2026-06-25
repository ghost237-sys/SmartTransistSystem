import { useState } from 'react'
import { verifyTicket } from '../../api/bookings'
import Button from '../../components/ui/Button'

export default function ScanPage() {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const handleScan = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const val = input.trim()
      const isShortCode = /^\d{6}$/.test(val)
      const payload = isShortCode
        ? { short_code: val }
        : { qr_code_token: val }
      const res = await verifyTicket(payload)
      setResult(res.data)
      setInput('')
    } catch (err) {
      const detail = err.response?.data?.detail || 'Verification failed.'
      setError(detail)
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setResult(null)
    setError('')
    setInput('')
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold text-amber" style={{ fontFamily: 'serif' }}>
        SCAN TICKET
      </h1>

      {result ? (
        <div className={`rounded-2xl p-8 text-center ${result.valid ? 'bg-green-500/20 border border-green-500/40' : 'bg-red-500/20 border border-red-500/40'}`}>
          <div className="text-6xl mb-4">{result.valid ? '✅' : '❌'}</div>
          {result.valid ? (
            <>
              <p className="text-green-400 font-bold text-2xl mb-2">VALID TICKET</p>
              <p className="text-white text-xl font-bold mb-1">{result.commuter}</p>
              <p className="text-white/60 text-sm">{result.boarding_stop} → {result.alighting_stop}</p>
            </>
          ) : (
            <>
              <p className="text-red-400 font-bold text-2xl mb-2">INVALID</p>
              <p className="text-white/70">{result.detail}</p>
            </>
          )}
          <Button className="mt-6 w-full" onClick={reset}>SCAN NEXT</Button>
        </div>
      ) : (
        <form onSubmit={handleScan} className="flex flex-col gap-4">
          <div>
            <p className="text-white/60 text-sm mb-2">Enter 6-digit code or paste QR token</p>
            <input
              type="text"
              placeholder="123456 or QR token"
              value={input}
              onChange={e => setInput(e.target.value)}
              className="w-full px-5 py-5 rounded-2xl bg-white/10 border-2 border-white/20 text-white placeholder-white/30 outline-none focus:border-amber text-2xl font-mono tracking-widest text-center"
              autoFocus
            />
          </div>

          {error && (
            <div className="bg-red-500/20 border border-red-500/40 rounded-xl px-4 py-3 text-center">
              <p className="text-red-400 font-bold">{error}</p>
            </div>
          )}

          <Button
            type="submit"
            loading={loading}
            disabled={!input.trim()}
            className="w-full py-5 text-xl"
          >
            VERIFY TICKET
          </Button>
        </form>
      )}
    </div>
  )
}