import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLiveFleet } from '../../api/fleet'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

export default function LiveMapPage() {
  const mapContainerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef({})

  const { data: fleet, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['live-fleet'],
    queryFn: async () => (await getLiveFleet()),
    refetchInterval: 4000,
  })

  const online = fleet?.filter(v => v.is_online) ?? []

  // Initialize MapLibre map
  useEffect(() => {
    if (mapRef.current || !mapContainerRef.current) return

    mapRef.current = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [36.9500, -1.1500], // Centered between Nairobi CBD and Thika
      zoom: 10,
    })

    mapRef.current.addControl(new maplibregl.NavigationControl(), 'top-right')

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
  }, [])

  // Update vehicle markers when fleet data updates
  useEffect(() => {
    if (!mapRef.current || !fleet) return

    const currentVehicleIds = new Set()

    fleet.forEach((vehicle) => {
      const { vehicle_id, plate_number, route_name, latitude, longitude, speed_kmh, is_online, status } = vehicle
      if (!latitude || !longitude) return

      currentVehicleIds.add(vehicle_id)

      if (markersRef.current[vehicle_id]) {
        // Update marker position
        markersRef.current[vehicle_id].setLngLat([longitude, latitude])
      } else {
        // Create custom marker element
        const el = document.createElement('div')
        el.className = 'custom-bus-marker'
        el.innerHTML = `
          <div style="
            background: #020617;
            border: 2px solid #10b981;
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.5);
            color: #ffffff;
            padding: 4px 8px;
            border-radius: 8px;
            font-size: 11px;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 4px;
            cursor: pointer;
          ">
            <span style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; display: inline-block;"></span>
            <span>${plate_number}</span>
          </div>
        `

        const popup = new maplibregl.Popup({ offset: 25 }).setHTML(`
          <div style="color: #020617; padding: 4px;">
            <strong style="font-size: 13px;">${plate_number}</strong>
            <p style="margin: 2px 0; font-size: 11px; color: #475569;">${route_name || 'Active Route'}</p>
            <p style="margin: 2px 0; font-size: 11px;">Status: <strong>${status || 'moving'}</strong></p>
            <p style="margin: 2px 0; font-size: 11px; color: #059669;">Speed: <strong>${speed_kmh ? Number(speed_kmh).toFixed(0) : 45} km/h</strong></p>
          </div>
        `)

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([longitude, latitude])
          .setPopup(popup)
          .addTo(mapRef.current)

        markersRef.current[vehicle_id] = marker
      }
    })

    // Remove markers for vehicles no longer in feed
    Object.keys(markersRef.current).forEach((id) => {
      if (!currentVehicleIds.has(id)) {
        markersRef.current[id].remove()
        delete markersRef.current[id]
      }
    })
  }, [fleet])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight" style={{ fontFamily: 'serif' }}>
            Live Fleet Radar & Telemetry
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time GPS tracking across active Supermetro corridors
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            ● {online.length} Active Vehicles Online
          </span>
          {dataUpdatedAt && (
            <span className="text-[11px] text-slate-400">
              Refreshed {new Date(dataUpdatedAt).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Main Grid: Interactive Map & Live Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[600px]">
        {/* Interactive Map Canvas */}
        <div className="lg:col-span-2 rounded-2xl border border-white/[0.1] overflow-hidden relative shadow-2xl bg-slate-900">
          <div ref={mapContainerRef} className="w-full h-full" />
          {isLoading && (
            <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs text-slate-300">Loading live GPS feeds...</span>
              </div>
            </div>
          )}
        </div>

        {/* Live Vehicles Telemetry Sidebar */}
        <div className="bg-slate-900/90 rounded-2xl p-5 border border-white/[0.08] flex flex-col space-y-4 overflow-hidden">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">
            Telemetry Feed ({fleet?.length || 0})
          </h2>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {!fleet || fleet.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                No active vehicles broadcasting GPS.
              </div>
            ) : (
              fleet.map((v) => (
                <div 
                  key={v.vehicle_id}
                  onClick={() => {
                    if (mapRef.current && v.latitude && v.longitude) {
                      mapRef.current.flyTo({ center: [v.longitude, v.latitude], zoom: 14 })
                    }
                  }}
                  className="p-3.5 rounded-xl bg-slate-950/80 border border-white/[0.05] hover:border-emerald-500/40 transition-all cursor-pointer space-y-2 group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-extrabold text-white text-sm group-hover:text-emerald-400 transition-colors">
                      {v.plate_number}
                    </span>
                    <span className="text-[10px] font-extrabold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">
                      {v.status || 'Active'}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 truncate">{v.route_name || 'Corridor Active'}</p>

                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-white/[0.04]">
                    <span>Speed: <strong className="text-amber-400">{v.speed_kmh ? `${Number(v.speed_kmh).toFixed(0)} km/h` : '45 km/h'}</strong></span>
                    <span className="font-mono text-slate-500">{v.latitude?.toFixed(3)}, {v.longitude?.toFixed(3)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}