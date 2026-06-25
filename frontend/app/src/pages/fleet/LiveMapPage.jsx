import { useQuery } from '@tanstack/react-query'
import { getLiveFleet } from '../../api/fleet'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'

export default function LiveMapPage() {
  const { data: fleet, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['live-fleet'],
    queryFn: async () => (await getLiveFleet()),
    refetchInterval: 5000,
  })

  const online = fleet?.filter(v => v.is_online) ?? []
  const offline = fleet?.filter(v => !v.is_online) ?? []

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-ink" style={{ fontFamily: 'serif' }}>Live Fleet</h1>
          <p className="text-ink-light mt-1">
            {online.length} vehicle{online.length !== 1 ? 's' : ''} online · refreshes every 5s
          </p>
        </div>
        {dataUpdatedAt && (
          <span className="text-xs text-ink-light">
            Last updated {new Date(dataUpdatedAt).toLocaleTimeString('en-KE')}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <svg className="animate-spin h-8 w-8 text-green-deep" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
        </div>
      )}

      {fleet?.length === 0 && (
        <Card className="text-center py-12">
          <div className="text-4xl mb-3">🚌</div>
          <p className="text-ink font-medium mb-1">No active trips right now</p>
          <p className="text-ink-light text-sm">Vehicles appear here when they're on a departed trip.</p>
        </Card>
      )}

      {online.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-ink-light uppercase tracking-wider mb-3">Online</h2>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {online.map(v => (
              <Card key={v.vehicle_id} className="border-green-200">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse" />
                      <span className="font-bold text-ink">{v.plate_number}</span>
                    </div>
                    <p className="text-sm text-ink-light mt-0.5">{v.route_name}</p>
                  </div>
                  <Badge variant="green">Online</Badge>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-green-pale rounded-lg p-2.5">
                    <p className="text-xs text-ink-light mb-0.5">Speed</p>
                    <p className="font-bold text-green-deep text-sm">
                      {v.speed_kmh ? `${Number(v.speed_kmh).toFixed(0)} km/h` : '—'}
                    </p>
                  </div>
                  <div className="bg-green-pale rounded-lg p-2.5">
                    <p className="text-xs text-ink-light mb-0.5">Position</p>
                    <p className="font-mono text-green-deep text-xs">
                      {v.latitude?.toFixed(3)}, {v.longitude?.toFixed(3)}
                    </p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {offline.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-ink-light uppercase tracking-wider mb-3">On Trip — Offline</h2>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {offline.map(v => (
              <Card key={v.vehicle_id} className="opacity-60">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-gray-300" />
                      <span className="font-bold text-ink">{v.plate_number}</span>
                    </div>
                    <p className="text-sm text-ink-light mt-0.5">{v.route_name}</p>
                  </div>
                  <Badge variant="gray">No signal</Badge>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}