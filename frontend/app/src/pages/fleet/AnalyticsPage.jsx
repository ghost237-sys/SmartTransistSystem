import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAnalytics, exportFinancials } from '../../api/fleet'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'

export default function AnalyticsPage() {
  const today = new Date().toISOString().split('T')[0]
  const [start, setStart] = useState(today.substring(0, 7) + '-01')
  const [end, setEnd] = useState(today)
  const [exporting, setExporting] = useState(false)

  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics', start, end],
    queryFn: async () => (await getAnalytics(start, end)),
  })

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await exportFinancials(start, end)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `fleet_revenue_${start}_${end}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-ink" style={{ fontFamily: 'serif' }}>Analytics</h1>
          <p className="text-ink-light mt-1">Revenue and occupancy by route</p>
        </div>
        <Button variant="secondary" onClick={handleExport} loading={exporting}>
          Export CSV
        </Button>
      </div>

      {/* Date range */}
      <Card>
        <div className="flex gap-4 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-light">From</label>
            <input
              type="date"
              value={start}
              onChange={e => setStart(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:border-green-mid"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-ink-light">To</label>
            <input
              type="date"
              value={end}
              onChange={e => setEnd(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:border-green-mid"
            />
          </div>
        </div>
      </Card>

      {isLoading && (
        <div className="flex justify-center py-12">
          <svg className="animate-spin h-8 w-8 text-green-deep" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
        </div>
      )}

      {analytics && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <p className="text-xs text-ink-light mb-1">Total Revenue</p>
              <p className="text-2xl font-bold text-green-deep" style={{ fontFamily: 'serif' }}>
                KES {Number(analytics.total_revenue).toLocaleString()}
              </p>
            </Card>
            <Card>
              <p className="text-xs text-ink-light mb-1">Passengers</p>
              <p className="text-2xl font-bold text-green-deep" style={{ fontFamily: 'serif' }}>
                {analytics.total_passengers.toLocaleString()}
              </p>
            </Card>
            <Card>
              <p className="text-xs text-ink-light mb-1">Trips</p>
              <p className="text-2xl font-bold text-green-deep" style={{ fontFamily: 'serif' }}>
                {analytics.total_trips}
              </p>
            </Card>
          </div>

          {/* Route breakdown */}
          {analytics.routes.length > 0 ? (
            <Card>
              <h3 className="font-semibold text-ink mb-4">By Route</h3>
              <div className="flex flex-col divide-y divide-gray-100">
                {analytics.routes.map(route => (
                  <div key={route.route_id} className="py-4 first:pt-0 last:pb-0">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold text-ink">{route.route_name}</p>
                      <p className="font-bold text-green-deep">KES {Number(route.total_revenue).toLocaleString()}</p>
                    </div>
                    <div className="flex gap-4 text-sm text-ink-light">
                      <span>{route.total_trips} trips</span>
                      <span>{route.total_passengers} passengers</span>
                      <span>{route.average_occupancy_percent}% avg occupancy</span>
                    </div>
                    {/* Occupancy bar */}
                    <div className="mt-2 h-1.5 bg-green-pale rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-deep rounded-full transition-all"
                        style={{ width: `${Math.min(route.average_occupancy_percent, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          ) : (
            <Card className="text-center py-10">
              <p className="text-ink-light">No completed trips in this date range.</p>
            </Card>
          )}
        </>
      )}
    </div>
  )
}