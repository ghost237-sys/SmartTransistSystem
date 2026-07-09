import QRCode from 'react-qr-code'
import Card from './ui/Card'
import Badge from './ui/Badge'

function statusVariant(status) {
  return {
    confirmed: 'green',
    held: 'amber',
    boarded: 'blue',
    cancelled: 'red',
    expired: 'gray',
  }[status] || 'gray'
}

export default function TicketDisplay({
  shortCode,
  qrCodeToken,
  status = 'confirmed',
  routeName,
  boardingStop,
  alightingStop,
  farePaid,
  compact = false,
}) {
  const hasTicket = shortCode && qrCodeToken && ['confirmed', 'boarded'].includes(status)

  if (!hasTicket) {
    return (
      <Card className="border-amber-200 bg-amber-50 text-center py-6">
        <div className="text-3xl mb-2">⏳</div>
        <p className="font-semibold text-ink mb-1">Waiting for payment</p>
        <p className="text-sm text-ink-light">
          Complete the M-Pesa prompt on your phone. Your boarding ticket will appear here once payment is confirmed.
        </p>
        {status && (
          <div className="mt-3">
            <Badge variant={statusVariant(status)}>{status}</Badge>
          </div>
        )}
      </Card>
    )
  }

  return (
    <Card className={`border-green-200 bg-green-50 ${compact ? '' : 'text-center py-6'}`}>
      {!compact && (
        <>
          <div className="flex items-center justify-center gap-2 mb-1">
            <h2 className="text-xl font-bold text-green-deep">Your Boarding Ticket</h2>
            <Badge variant={statusVariant(status)}>{status}</Badge>
          </div>
          <p className="text-sm text-ink-light mb-5">
            Show this QR code or tell the conductor your 6-digit code when boarding.
          </p>
        </>
      )}

      <div className={`flex ${compact ? 'flex-col sm:flex-row sm:items-center gap-4' : 'flex-col items-center gap-5'}`}>
        <div className="bg-white p-4 rounded-2xl shadow-sm inline-flex mx-auto">
          <QRCode
            value={qrCodeToken}
            size={compact ? 128 : 180}
            level="M"
            bgColor="#ffffff"
            fgColor="#1a472a"
          />
        </div>

        <div className={compact ? 'flex-1' : 'w-full'}>
          <p className="text-xs text-ink-light mb-1 uppercase tracking-wide">Backup code</p>
          <p
            className={`font-mono font-bold text-green-deep tracking-[0.35em] ${
              compact ? 'text-2xl' : 'text-4xl'
            }`}
          >
            {shortCode}
          </p>
          {!compact && (
            <p className="text-xs text-ink-light mt-2">
              Conductor can scan the QR or type this code manually.
            </p>
          )}
        </div>
      </div>

      {(routeName || boardingStop || alightingStop || farePaid) && (
        <div className={`mt-5 pt-5 border-t border-green-200 ${compact ? 'text-sm' : ''}`}>
          <div className="flex flex-col gap-2 text-sm">
            {routeName && (
              <div className="flex justify-between gap-4">
                <span className="text-ink-light">Route</span>
                <span className="font-medium text-ink text-right">{routeName}</span>
              </div>
            )}
            {boardingStop && (
              <div className="flex justify-between gap-4">
                <span className="text-ink-light">Board at</span>
                <span className="font-medium text-ink text-right">{boardingStop}</span>
              </div>
            )}
            {alightingStop && (
              <div className="flex justify-between gap-4">
                <span className="text-ink-light">Alighting at</span>
                <span className="font-medium text-ink text-right">{alightingStop}</span>
              </div>
            )}
            {farePaid != null && (
              <div className="flex justify-between gap-4">
                <span className="text-ink-light">Fare paid</span>
                <span className="font-medium text-ink">KES {Number(farePaid).toLocaleString()}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}
