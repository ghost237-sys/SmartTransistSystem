import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAnalytics, exportFinancials } from '../../api/fleet'

export default function AnalyticsPage() {
  const today = new Date().toISOString().split('T')[0]
  const [start, setStart] = useState(today.substring(0, 7) + '-01')
  const [end, setEnd] = useState(today)
  const [selectedRoute, setSelectedRoute] = useState('ALL')
  const [paymentChannel, setPaymentChannel] = useState('ALL')
  const [exporting, setExporting] = useState(false)

  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics', start, end],
    queryFn: async () => (await getAnalytics(start, end)),
  })

  // Presets
  const handlePreset = (type) => {
    const d = new Date()
    if (type === 'TODAY') {
      setStart(today)
      setEnd(today)
    } else if (type === 'THIS_WEEK') {
      const day = d.getDay()
      const diff = d.getDate() - day + (day === 0 ? -6 : 1)
      const monday = new Date(d.setDate(diff)).toISOString().split('T')[0]
      setStart(monday)
      setEnd(today)
    } else if (type === 'THIS_MONTH') {
      setStart(today.substring(0, 7) + '-01')
      setEnd(today)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await exportFinancials(start, end)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `supermetro_financial_report_${start}_to_${end}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  // Filter routes
  const filteredRoutes = useMemo(() => {
    if (!analytics?.routes) return []
    let list = analytics.routes
    if (selectedRoute !== 'ALL') {
      list = list.filter(r => r.route_id === selectedRoute || r.route_name.includes(selectedRoute))
    }
    return list
  }, [analytics, selectedRoute])

  // Filtered Totals
  const totalRevenue = useMemo(() => {
    let rev = filteredRoutes.reduce((acc, r) => acc + Number(r.total_revenue || 0), 0)
    if (paymentChannel === 'DIGITAL') rev *= 0.88
    if (paymentChannel === 'CASH') rev *= 0.12
    return rev
  }, [filteredRoutes, paymentChannel])

  const totalPax = useMemo(() => {
    return filteredRoutes.reduce((acc, r) => acc + Number(r.total_passengers || 0), 0)
  }, [filteredRoutes])

  const leakageRecovered = totalRevenue * 0.12
  const subscriptionCost = totalPax * 15
  const netProfit = totalRevenue - (filteredRoutes.reduce((acc, r) => acc + (r.total_trips * 2800), 0))

  return (
    <div className="space-y-8 text-slate-100 min-h-screen">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-6">
        <div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight" style={{ fontFamily: 'serif' }}>
            Financial Intelligence & Audit Hub
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Filter revenue streams, leakage metrics, subscription ROI, and corridor yields
          </p>
        </div>

        <button
          onClick={handleExport}
          disabled={exporting}
          className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-extrabold px-5 py-2.5 rounded-xl text-sm transition-all flex items-center gap-2 cursor-pointer shadow-lg shadow-emerald-500/10"
        >
          <span>📥</span> {exporting ? 'Generating Report...' : 'Export Financial CSV'}
        </button>
      </div>

      {/* Filter Control Console */}
      <div className="bg-slate-900/90 rounded-2xl p-6 border border-white/[0.08] space-y-5">
        <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <span>⚙️</span> Financial Filter Parameters
          </h2>
          <div className="flex gap-2">
            {['TODAY', 'THIS_WEEK', 'THIS_MONTH'].map((preset) => (
              <button
                key={preset}
                onClick={() => handlePreset(preset)}
                className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-white/[0.05] transition-colors cursor-pointer"
              >
                {preset.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Start Date */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">From Date</label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">To Date</label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* Corridor Filter */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Route Corridor</label>
            <select
              value={selectedRoute}
              onChange={(e) => setSelectedRoute(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:border-emerald-500"
            >
              <option value="ALL">All Route Corridors</option>
              {analytics?.routes?.map((r) => (
                <option key={r.route_id} value={r.route_id}>
                  {r.route_name}
                </option>
              ))}
            </select>
          </div>

          {/* Payment Channel */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Payment Channel</label>
            <select
              value={paymentChannel}
              onChange={(e) => setPaymentChannel(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:border-emerald-500"
            >
              <option value="ALL">All Payment Methods</option>
              <option value="DIGITAL">Digital (M-Pesa / Pass) — 88%</option>
              <option value="CASH">Cash Handover Audit — 12%</option>
            </select>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {analytics && (
        <>
          {/* Filtered Financial Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 rounded-2xl bg-slate-900/90 border border-emerald-500/20">
              <span className="text-xs font-semibold uppercase text-slate-400">Filtered Gross Revenue</span>
              <p className="text-3xl font-extrabold text-emerald-400 mt-2" style={{ fontFamily: 'serif' }}>
                KES {totalRevenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
              <p className="text-xs text-slate-400 mt-1">Period: {start} to {end}</p>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-amber-500/20">
              <span className="text-xs font-semibold uppercase text-slate-400">Estimated Leakage Recovered</span>
              <p className="text-3xl font-extrabold text-amber-400 mt-2" style={{ fontFamily: 'serif' }}>
                KES {leakageRecovered.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
              <p className="text-xs text-slate-400 mt-1">12% baseline cash recovery</p>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-cyan-500/20">
              <span className="text-xs font-semibold uppercase text-slate-400">Usage Subscription Charge</span>
              <p className="text-3xl font-extrabold text-cyan-400 mt-2" style={{ fontFamily: 'serif' }}>
                KES {subscriptionCost.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
              <p className="text-xs text-slate-400 mt-1">{totalPax.toLocaleString()} passengers @ KES 15/pax</p>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/90 border border-purple-500/20">
              <span className="text-xs font-semibold uppercase text-slate-400">Estimated Net Yield</span>
              <p className="text-3xl font-extrabold text-white mt-2" style={{ fontFamily: 'serif' }}>
                KES {Math.max(0, netProfit).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
              <p className="text-xs text-slate-400 mt-1">Net after fuel & daily crew rates</p>
            </div>
          </div>

          {/* Filtered Corridor Breakdown Table */}
          <div className="bg-slate-900/90 rounded-2xl p-6 border border-white/[0.08] space-y-4">
            <h2 className="text-lg font-bold text-white">Financial Breakdown by Corridor</h2>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-950/80 text-xs uppercase tracking-wider text-slate-400 border-b border-white/[0.08]">
                  <tr>
                    <th className="py-3 px-4">Route Corridor</th>
                    <th className="py-3 px-4">Total Trips</th>
                    <th className="py-3 px-4">Passengers Boarded</th>
                    <th className="py-3 px-4">Avg Load Factor</th>
                    <th className="py-3 px-4">Gross Revenue</th>
                    <th className="py-3 px-4 text-right">Net Profit Yield</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.05]">
                  {filteredRoutes.map((route) => (
                    <tr key={route.route_id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3.5 px-4 font-bold text-white">{route.route_name}</td>
                      <td className="py-3.5 px-4 text-slate-400">{route.total_trips}</td>
                      <td className="py-3.5 px-4 text-slate-400">{route.total_passengers.toLocaleString()}</td>
                      <td className="py-3.5 px-4 font-semibold text-slate-200">{route.average_occupancy_percent}%</td>
                      <td className="py-3.5 px-4 font-bold text-emerald-400">
                        KES {Number(route.total_revenue).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4 text-right font-bold text-white">
                        KES {Number(route.estimated_net_profit || (route.total_revenue * 0.45)).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}