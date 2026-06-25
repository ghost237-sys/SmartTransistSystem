import { useQuery } from '@tanstack/react-query'
import { getAnalytics, getDocumentAlerts, getLiveFleet } from '../../api/fleet'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import { useNavigate } from 'react-router-dom'

function StatCard({ label, value, sub, color = 'green' }) {
  const colors = {
    green: 'text-green-deep',
    amber: 'text-amber-dark',
    red: 'text-red-600',
  }
  return (
    <Card>
      <p className="text-xs text-ink-light mb-1">{label}</p>
      <p className={`text-3xl font-bold ${colors[color]}`} style={{ fontFamily: 'serif' }}>{value}</p>
      {sub && <p className="text-xs text-ink-light mt-1">{sub}</p>}
    </Card>
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

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
          Overview
        </h1>
        <p className="text-ink-light mt-1">Month to date performance</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Total Revenue"
          value={analytics ? `KES ${Number(analytics.total_revenue).toLocaleString()}` : '—'}
          sub="This month"
        />
        <StatCard
          label="Passengers"
          value={analytics?.total_passengers ?? '—'}
          sub="Boarded this month"
        />
        <StatCard
          label="Trips Completed"
          value={analytics?.total_trips ?? '—'}
          sub="This month"
        />
        <StatCard
          label="Vehicles Online"
          value={onlineCount}
          sub="Active right now"
          color={onlineCount > 0 ? 'green' : 'amber'}
        />
      </div>

      {/* Document alerts */}
      {alertCount > 0 && (
        <Card className="border-red-200 bg-red-50">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-red-700">Document Alerts</h3>
            <Badge variant="red">{alertCount} vehicle{alertCount > 1 ? 's' : ''}</Badge>
          </div>
          <div className="flex flex-col gap-2">
            {alerts.alerts.map(a => (
              <div key={a.vehicle_id} className="flex items-center justify-between text-sm">
                <span className="font-medium text-ink">{a.plate_number}</span>
                <div className="flex gap-2">
                  {a.alerts.map((al, i) => (
                    <Badge key={i} variant={al.severity === 'expired' ? 'red' : 'amber'}>
                      {al.type} {al.severity === 'expired' ? 'expired' : `expires ${al.expiry}`}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Live fleet preview */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-ink">Live Fleet</h2>
          <button
            onClick={() => navigate('/fleet/live')}
            className="text-sm text-green-mid hover:text-green-deep font-medium transition-colors"
          >
            View all →
          </button>
        </div>
        {!liveFleet || liveFleet.length === 0 ? (
          <Card className="text-center py-8">
            <p className="text-ink-light text-sm">No vehicles currently on active trips.</p>
          </Card>
        ) : (
          <div className="flex flex-col gap-3">
            {liveFleet.slice(0, 3).map(v => (
              <Card key={v.vehicle_id}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-ink">{v.plate_number}</p>
                    <p className="text-sm text-ink-light">{v.route_name}</p>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-1.5 justify-end mb-1">
                      <span className={`w-2 h-2 rounded-full ${v.is_online ? 'bg-green-500' : 'bg-gray-300'}`} />
                      <span className="text-xs text-ink-light">{v.is_online ? 'Online' : 'Offline'}</span>
                    </div>
                    {v.speed_kmh && (
                      <span className="text-sm font-medium text-amber-dark">{Number(v.speed_kmh).toFixed(0)} km/h</span>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Route breakdown */}
      {analytics?.routes?.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-ink mb-3">Routes This Month</h2>
          <Card>
            <div className="flex flex-col divide-y divide-gray-100">
              {analytics.routes.map(route => (
                <div key={route.route_id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                  <div>
                    <p className="font-medium text-ink text-sm">{route.route_name}</p>
                    <p className="text-xs text-ink-light">{route.total_trips} trips · {route.total_passengers} passengers</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-ink text-sm">KES {Number(route.total_revenue).toLocaleString()}</p>
                    <p className="text-xs text-ink-light">{route.average_occupancy_percent}% occupancy</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}