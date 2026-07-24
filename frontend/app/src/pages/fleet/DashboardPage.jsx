import { useQuery } from '@tanstack/react-query'
import { getAnalytics, getDocumentAlerts, getLiveFleet } from '../../api/fleet'
import { useNavigate } from 'react-router-dom'

function ExecutiveStatCard({ label, value, sub, color = 'emerald', icon }) {
  const colorStyles = {
    emerald: 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5',
    gold: 'text-amber-400 border-amber-500/20 bg-amber-500/5',
    cyan: 'text-cyan-400 border-cyan-500/20 bg-cyan-500/5',
    rose: 'text-rose-400 border-rose-500/20 bg-rose-500/5',
  }

  return (
    <div className={`p-5 rounded-2xl border backdrop-blur-md transition-all hover:scale-[1.01] ${colorStyles[color] || colorStyles.emerald}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</span>
        {icon && <div className="p-2 rounded-xl bg-white/5 text-slate-300">{icon}</div>}
      </div>
      <p className="text-3xl font-extrabold tracking-tight text-white mb-1" style={{ fontFamily: 'serif' }}>
        {value}
      </p>
      {sub && <p className="text-xs text-slate-400 font-medium">{sub}</p>}
    </div>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const today = new Date().toISOString().split('T')[0]
  const monthStart = today.substring(0, 7) + '-01'

  const { data: analytics } = useQuery({
    queryKey: ['analytics', monthStart, today],
    queryFn: async () => (await getAnalytics(monthStart, today)),
  })

  const { data: liveFleet } = useQuery({
    queryKey: ['live-fleet'],
    queryFn: async () => (await getLiveFleet()),
    refetchInterval: 5000,
  })

  const { data: alerts } = useQuery({
    queryKey: ['document-alerts'],
    queryFn: async () => (await getDocumentAlerts()),
  })

  const onlineCount = liveFleet?.filter(v => v.is_online).length ?? 0
  const alertCount = alerts?.alerts?.length ?? 0

  const totalRev = Number(analytics?.total_revenue || 0)
  const totalPax = Number(analytics?.total_passengers || 0)
  
  // BI calculations
  const leakagePrevented = analytics?.estimated_leakage_prevented ?? (totalRev * 0.12)
  const subscriptionCost = analytics?.total_subscription_cost ?? (totalPax * 15)
  const netValueAdded = analytics?.net_subscription_roi ?? (leakagePrevented - subscriptionCost)
  const avgOccupancy = analytics?.routes?.length 
    ? (analytics.routes.reduce((acc, r) => acc + r.average_occupancy_percent, 0) / analytics.routes.length).toFixed(1)
    : 0

  return (
    <div className="-mx-4 -my-6 px-4 py-6 min-h-screen text-slate-100" style={{ background: '#020617' }}>
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Top Header & Live Fleet Counter */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-6">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-extrabold text-white tracking-tight" style={{ fontFamily: 'serif' }}>
                Executive Fleet Command
              </h1>
              <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Supermetro Tenant
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-1">
              Real-time financial audit, route yield analysis, and fleet telemetry
            </p>
          </div>

          <div className="flex items-center gap-3 bg-slate-900/80 p-2.5 px-4 rounded-2xl border border-white/[0.08]">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <div>
              <p className="text-xs text-slate-400">Live Active Fleet</p>
              <p className="text-sm font-bold text-white">{onlineCount} Vehicles Online</p>
            </div>
          </div>
        </div>

        {/* 1. Executive Metrics Grid (4 Key Cards) */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <ExecutiveStatCard
            label="Gross Fare Revenue"
            value={analytics ? `KES ${totalRev.toLocaleString()}` : '—'}
            sub={`${analytics?.total_trips || 0} trips completed this month`}
            color="emerald"
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33" />
              </svg>
            }
          />

          <ExecutiveStatCard
            label="Revenue Leakage Prevented"
            value={analytics ? `KES ${Number(leakagePrevented).toLocaleString()}` : '—'}
            sub="Est. 12% cash gap recovered by digital audit"
            color="gold"
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            }
          />

          <ExecutiveStatCard
            label="Subscription ROI Net Benefit"
            value={analytics ? `KES ${Number(netValueAdded).toLocaleString()}` : '—'}
            sub={`Fee: KES 15/commuter (${totalPax.toLocaleString()} pax)`}
            color="cyan"
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            }
          />

          <ExecutiveStatCard
            label="Fleet Load Factor"
            value={`${avgOccupancy}%`}
            sub="Benchmark: Top Supermetro routes run @ 84%"
            color={Number(avgOccupancy) >= 70 ? 'emerald' : 'gold'}
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            }
          />
        </div>

        {/* 2. Financial Leakage Audit Module & Platform ROI Card */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-slate-900/90 rounded-2xl p-6 border border-white/[0.08] space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white">Revenue Leakage & Collection Audit</h2>
                <p className="text-xs text-slate-400">Digital tracking vs manual cash risks across fleet operations</p>
              </div>
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                12% Est. Recovery
              </span>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs font-semibold mb-1.5">
                  <span className="text-emerald-400">Digital Fare Capture (Direct M-Pesa / Pass) — 88%</span>
                  <span className="text-slate-300">KES {(totalRev * 0.88).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                </div>
                <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full" style={{ width: '88%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold mb-1.5">
                  <span className="text-amber-400 font-medium">Estimated Recovered Cash Leakage — 12%</span>
                  <span className="text-slate-300">KES {Number(leakagePrevented).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                </div>
                <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-amber-500 to-amber-400 rounded-full" style={{ width: '12%' }} />
                </div>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-white/[0.04] flex items-start gap-3">
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 shrink-0">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                <strong className="text-white">Business Impact:</strong> Digital QR boarding and seat reservations capture 88% of passenger fare upfront, eliminating manual ticket skimming and adding an estimated <strong className="text-emerald-400">KES {Number(leakagePrevented).toLocaleString()}</strong> in recovered revenue this month.
              </p>
            </div>
          </div>

          {/* Subscription ROI Proof Card */}
          <div className="bg-slate-900/90 rounded-2xl p-6 border border-white/[0.08] flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-white">Platform ROI Calculator</h2>
                <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-md">
                  Per-Commuter Model
                </span>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between items-center text-sm py-2 border-b border-white/[0.05]">
                  <span className="text-slate-400">Recovered Leakage</span>
                  <span className="font-bold text-emerald-400">+ KES {Number(leakagePrevented).toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center text-sm py-2 border-b border-white/[0.05]">
                  <span className="text-slate-400">App Commuters Boarded</span>
                  <span className="font-bold text-white">{totalPax.toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center text-sm py-2 border-b border-white/[0.05]">
                  <span className="text-slate-400">Platform Charge (KES 15/pax)</span>
                  <span className="font-bold text-rose-400">- KES {Number(subscriptionCost).toLocaleString()}</span>
                </div>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-center space-y-1">
              <span className="text-xs uppercase font-bold text-emerald-400 tracking-wider">Monthly Net Profit Added</span>
              <p className="text-2xl font-extrabold text-white" style={{ fontFamily: 'serif' }}>
                KES {Number(netValueAdded).toLocaleString()}
              </p>
              <p className="text-[11px] text-emerald-300">Your subscription pays for itself via recovered leakage!</p>
            </div>
          </div>
        </div>

        {/* 3. Route Yield Analysis Table */}
        <div className="bg-slate-900/90 rounded-2xl p-6 border border-white/[0.08] space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white">Route Corridor Yield & Net Profitability</h2>
              <p className="text-xs text-slate-400">Breakdown by route revenue, trips, load factor, and estimated net profit</p>
            </div>
            <button
              onClick={() => navigate('/fleet/analytics')}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              Full Analytics →
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/80 text-xs uppercase tracking-wider text-slate-400 border-b border-white/[0.08]">
                <tr>
                  <th className="py-3 px-4">Route Corridor</th>
                  <th className="py-3 px-4">Trips Completed</th>
                  <th className="py-3 px-4">Passengers</th>
                  <th className="py-3 px-4">Gross Fare</th>
                  <th className="py-3 px-4">Load Factor</th>
                  <th className="py-3 px-4 text-right">Est. Net Profit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {analytics?.routes?.map((route) => (
                  <tr key={route.route_id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-white">{route.route_name}</td>
                    <td className="py-3.5 px-4 text-slate-400">{route.total_trips}</td>
                    <td className="py-3.5 px-4 text-slate-400">{route.total_passengers.toLocaleString()}</td>
                    <td className="py-3.5 px-4 font-bold text-emerald-400">KES {Number(route.total_revenue).toLocaleString()}</td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${route.average_occupancy_percent >= 75 ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                        <span className="font-semibold">{route.average_occupancy_percent}%</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right font-bold text-white">
                      KES {Number(route.estimated_net_profit || (route.total_revenue * 0.4)).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 4. Active Fleet & Document Alerts Side-by-Side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Live Fleet Preview */}
          <div className="bg-slate-900/90 rounded-2xl p-6 border border-white/[0.08] space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Active Fleet Telemetry</h2>
              <button
                onClick={() => navigate('/fleet/live')}
                className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition-colors"
              >
                Open Live Map →
              </button>
            </div>

            {!liveFleet || liveFleet.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">
                No vehicles currently on active trips.
              </div>
            ) : (
              <div className="space-y-3">
                {liveFleet.slice(0, 4).map((v) => (
                  <div key={v.vehicle_id} className="p-3.5 rounded-xl bg-slate-950/60 border border-white/[0.05] flex items-center justify-between">
                    <div>
                      <p className="font-bold text-white text-sm">{v.plate_number}</p>
                      <p className="text-xs text-slate-400">{v.route_name}</p>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center gap-1.5 justify-end mb-1">
                        <span className={`w-2 h-2 rounded-full ${v.is_online ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                        <span className="text-xs font-medium text-slate-300">{v.status}</span>
                      </div>
                      <span className="text-xs font-bold text-amber-400">{v.speed_kmh ? `${Number(v.speed_kmh).toFixed(0)} km/h` : 'Stopped'}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Document Compliance Alerts */}
          <div className="bg-slate-900/90 rounded-2xl p-6 border border-white/[0.08] space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Compliance & Renewal Alerts</h2>
              <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
                {alertCount} Alerts
              </span>
            </div>

            {alertCount === 0 ? (
              <div className="p-6 text-center text-slate-400 text-sm bg-slate-950/40 rounded-xl border border-white/[0.04]">
                ✓ All vehicle insurance & inspection compliance up to date.
              </div>
            ) : (
              <div className="space-y-3">
                {alerts.alerts.map((a) => (
                  <div key={a.vehicle_id} className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-500/20 flex items-center justify-between">
                    <div>
                      <span className="font-bold text-white text-sm">{a.plate_number}</span>
                      <p className="text-xs text-slate-400">Grounded if non-compliant</p>
                    </div>
                    <div className="flex gap-2">
                      {a.alerts.map((al, i) => (
                        <span key={i} className={`text-xs px-2.5 py-1 rounded-lg font-semibold ${al.severity === 'expired' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'}`}>
                          {al.type} {al.severity === 'expired' ? 'EXPIRED' : `exp: ${al.expiry}`}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}