import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { getDriverTrips, getDriverTrip, getTripStops } from '../../api/trips'
import { getTripManifest } from '../../api/bookings'
import {
  Users,
  MapPin,
  Clock,
  AlertTriangle,
  Zap,
  ShieldAlert,
  Wrench,
  ChevronRight,
  Radio,
  Navigation,
  LogOut
} from 'lucide-react'

// ─── Simulated headway data (would come from dispatch websocket in production) ──
function useHeadwaySimulation() {
  const [headway, setHeadway] = useState({
    ahead: { minutes: 4, label: 'Bus Ahead' },
    behind: { minutes: 6, label: 'Bus Behind' },
    status: 'on_time', // 'on_time' | 'bunching' | 'gap'
    targetSpacing: 5,
  })

  useEffect(() => {
    const interval = setInterval(() => {
      setHeadway(prev => {
        const aheadDrift = (Math.random() - 0.5) * 0.4
        const behindDrift = (Math.random() - 0.5) * 0.4
        const newAhead = Math.max(1, Math.round((prev.ahead.minutes + aheadDrift) * 10) / 10)
        const newBehind = Math.max(1, Math.round((prev.behind.minutes + behindDrift) * 10) / 10)
        let status = 'on_time'
        if (newAhead < 2 || newBehind < 2) status = 'bunching'
        else if (newAhead > 8 || newBehind > 8) status = 'gap'
        return {
          ahead: { minutes: newAhead, label: 'Bus Ahead' },
          behind: { minutes: newBehind, label: 'Bus Behind' },
          status,
          targetSpacing: 5,
        }
      })
    }, 4000)
    return () => clearInterval(interval)
  }, [])

  return headway
}

// ─── Clock component ──
function LiveClock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="font-mono text-[#f1a81f] text-sm font-bold tabular-nums">
      {time.toLocaleTimeString('en-KE', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
    </span>
  )
}

export default function DriverDashboardPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [activeTrip, setActiveTrip] = useState(null)
  const [reportModal, setReportModal] = useState(null) // null | 'traffic' | 'police' | 'breakdown'
  const [reportSent, setReportSent] = useState(null)
  const reportTimeout = useRef(null)

  const headway = useHeadwaySimulation()

  // Load driver's active trips
  const { data: trips, isLoading: loadingTrips } = useQuery({
    queryKey: ['driver-trips'],
    queryFn: async () => (await getDriverTrips()).data,
    refetchInterval: 30000,
  })

  // Auto-select first active trip
  useEffect(() => {
    if (trips?.length && !activeTrip) {
      setActiveTrip(trips[0])
    }
  }, [trips])

  // Load trip detail
  const { data: tripDetail } = useQuery({
    queryKey: ['driver-trip-detail', activeTrip?.id],
    queryFn: async () => (await getDriverTrip(activeTrip.id)).data,
    enabled: !!activeTrip?.id,
    refetchInterval: 10000,
  })

  // Load trip stops for next-stop calculation
  const { data: stops } = useQuery({
    queryKey: ['trip-stops', activeTrip?.id],
    queryFn: async () => (await getTripStops(activeTrip.id)).data,
    enabled: !!activeTrip?.id,
  })

  // Load manifest for headcount
  const { data: manifest } = useQuery({
    queryKey: ['manifest', activeTrip?.id],
    queryFn: async () => getTripManifest(activeTrip.id),
    enabled: !!activeTrip?.id,
    refetchInterval: 5000,
  })

  const boarded = manifest?.manifest?.filter(b => b.status === 'boarded').length ?? 0
  const confirmed = manifest?.manifest?.filter(b => b.status === 'confirmed').length ?? 0
  const totalOnboard = boarded + confirmed

  // Next stop logic (simulate progress through stops)
  const [currentStopIndex, setCurrentStopIndex] = useState(0)
  const nextStop = stops?.[currentStopIndex + 1] || stops?.[stops?.length - 1]
  const dropOffsAtNext = manifest?.manifest?.filter(
    b => b.alighting_stop === nextStop?.name && b.status === 'boarded'
  ).length ?? 0

  // Simulate ETA to next stop
  const [nextStopEta, setNextStopEta] = useState(3)
  useEffect(() => {
    const interval = setInterval(() => {
      setNextStopEta(prev => {
        const next = Math.max(0.5, prev + (Math.random() - 0.55) * 0.3)
        return Math.round(next * 10) / 10
      })
    }, 5000)
    return () => clearInterval(interval)
  }, [nextStop])

  // Quick report handler
  const handleReport = (type) => {
    setReportModal(null)
    setReportSent(type)
    if (reportTimeout.current) clearTimeout(reportTimeout.current)
    reportTimeout.current = setTimeout(() => setReportSent(null), 4000)
  }

  // Headway status styling
  const headwayColor = {
    on_time: { bg: 'bg-emerald-500/15', border: 'border-emerald-500/30', text: 'text-emerald-400', label: 'ON TIME', dot: 'bg-emerald-400' },
    bunching: { bg: 'bg-amber-500/15', border: 'border-amber-500/30', text: 'text-amber-400', label: 'BUNCHING', dot: 'bg-amber-400' },
    gap: { bg: 'bg-red-500/15', border: 'border-red-500/30', text: 'text-red-400', label: 'GAP WARNING', dot: 'bg-red-400' },
  }[headway.status]

  const routeName = tripDetail?.route_name || activeTrip?.route_name || '—'
  const vehiclePlate = tripDetail?.vehicle_plate || activeTrip?.vehicle_plate || '—'
  const fleetCode = tripDetail?.fleet_code || activeTrip?.fleet_code || ''

  if (loadingTrips) {
    return (
      <div className="fixed inset-0 bg-[#090d16] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <svg className="animate-spin h-10 w-10 text-[#f1a81f]" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-white/50 text-xs uppercase tracking-widest font-bold">Loading Dashboard</p>
        </div>
      </div>
    )
  }

  if (!trips?.length) {
    return (
      <div className="fixed inset-0 bg-[#090d16] flex items-center justify-center p-6">
        <div className="text-center">
          <div className="w-20 h-20 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-6">
            <Navigation className="w-10 h-10 text-white/20" />
          </div>
          <h2 className="text-white text-2xl font-bold mb-2" style={{ fontFamily: 'serif' }}>No Active Trips</h2>
          <p className="text-white/40 text-sm max-w-xs mx-auto">
            Your fleet manager has not assigned an active trip to you yet. This dashboard will activate automatically when a trip begins.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-[#090d16] flex flex-col overflow-hidden select-none">

      {/* ═══════ PERSISTENT HEADER ═══════ */}
      <header className="bg-black/40 border-b border-white/[0.06] px-4 py-3 flex items-center justify-between shrink-0 backdrop-blur-sm z-20">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-[#f1a81f]/15 border border-[#f1a81f]/30 flex items-center justify-center shrink-0">
            <Radio className="w-4.5 h-4.5 text-[#f1a81f]" />
          </div>
          <div className="min-w-0">
            <h1 className="text-white font-black text-base truncate leading-tight tracking-tight">
              {routeName}
            </h1>
            <p className="text-white/40 text-[11px] font-bold uppercase tracking-wider truncate">
              {fleetCode && `${fleetCode} · `}{vehiclePlate}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <LiveClock />
          {/* Headcount pill */}
          <div className="flex items-center gap-1.5 bg-white/[0.06] border border-white/10 rounded-full px-3 py-1.5">
            <Users className="w-4 h-4 text-[#f1a81f]" />
            <span className="text-white font-black text-lg tabular-nums leading-none">{totalOnboard}</span>
            <span className="text-white/30 text-[10px] font-bold uppercase">PAX</span>
          </div>
          {/* Logout */}
          <button
            onClick={() => { logout(); navigate('/login'); }}
            className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.08] hover:bg-red-500/15 hover:border-red-500/30 flex items-center justify-center transition-all cursor-pointer group"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5 text-white/25 group-hover:text-red-400 transition-colors" />
          </button>
        </div>
      </header>

      {/* ═══════ MAIN SPLIT GRID ═══════ */}
      <div className="flex-1 flex min-h-0">

        {/* ─── LEFT PANEL: HEADWAY TIMER (50%) ─── */}
        <div className="w-1/2 border-r border-white/[0.06] flex flex-col p-4 gap-4">

          {/* Headway status badge */}
          <div className={`${headwayColor.bg} ${headwayColor.border} border rounded-xl px-4 py-2.5 flex items-center justify-between`}>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${headwayColor.dot} animate-pulse`} />
              <span className={`text-[10px] font-black uppercase tracking-widest ${headwayColor.text}`}>
                Spacing: {headwayColor.label}
              </span>
            </div>
            <span className="text-white/30 text-[10px] font-bold">
              Target: {headway.targetSpacing}m
            </span>
          </div>

          {/* Giant headway display */}
          <div className="flex-1 flex flex-col justify-center gap-6">
            {/* Bus ahead */}
            <div className="flex flex-col items-center gap-1">
              <span className="text-white/30 text-[10px] font-black uppercase tracking-[0.2em]">
                Bus Ahead
              </span>
              <div className="flex items-baseline gap-1">
                <span className="text-[#f1a81f] font-black tabular-nums leading-none"
                  style={{ fontSize: 'clamp(2.5rem, 8vw, 4.5rem)' }}>
                  {headway.ahead.minutes.toFixed(1)}
                </span>
                <span className="text-white/25 text-lg font-bold">min</span>
              </div>
              <div className="w-full max-w-[200px] h-1.5 bg-white/[0.06] rounded-full overflow-hidden mt-1">
                <div
                  className="h-full bg-[#f1a81f]/60 rounded-full transition-all duration-1000"
                  style={{ width: `${Math.min(100, (headway.ahead.minutes / 10) * 100)}%` }}
                />
              </div>
            </div>

            {/* Divider */}
            <div className="flex items-center gap-3 px-4">
              <div className="flex-1 h-px bg-white/[0.06]" />
              <div className="w-8 h-8 rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center">
                <Zap className="w-3.5 h-3.5 text-[#f1a81f]/60" />
              </div>
              <div className="flex-1 h-px bg-white/[0.06]" />
            </div>

            {/* Bus behind */}
            <div className="flex flex-col items-center gap-1">
              <span className="text-white/30 text-[10px] font-black uppercase tracking-[0.2em]">
                Bus Behind
              </span>
              <div className="flex items-baseline gap-1">
                <span className="text-white font-black tabular-nums leading-none"
                  style={{ fontSize: 'clamp(2.5rem, 8vw, 4.5rem)' }}>
                  {headway.behind.minutes.toFixed(1)}
                </span>
                <span className="text-white/25 text-lg font-bold">min</span>
              </div>
              <div className="w-full max-w-[200px] h-1.5 bg-white/[0.06] rounded-full overflow-hidden mt-1">
                <div
                  className="h-full bg-white/20 rounded-full transition-all duration-1000"
                  style={{ width: `${Math.min(100, (headway.behind.minutes / 10) * 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* ─── RIGHT PANEL (50%) ─── */}
        <div className="w-1/2 flex flex-col">

          {/* ─── RIGHT TOP: NEXT STOP HUB ─── */}
          <div className="flex-1 border-b border-white/[0.06] p-4 flex flex-col justify-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
                <MapPin className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <span className="text-white/30 text-[10px] font-black uppercase tracking-[0.15em]">
                Next Stop
              </span>
            </div>

            <div>
              <h2 className="text-white font-black truncate leading-tight"
                style={{ fontSize: 'clamp(1.1rem, 3.5vw, 1.6rem)' }}>
                {nextStop?.name || 'End of Line'}
              </h2>
              {nextStop?.name && (
                <p className="text-white/30 text-[11px] font-bold mt-1 uppercase tracking-wider">
                  Stop {(currentStopIndex + 2)} of {stops?.length || '—'}
                </p>
              )}
            </div>

            <div className="flex gap-3">
              {/* ETA */}
              <div className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl p-3 text-center">
                <div className="flex items-center justify-center gap-1.5 mb-1">
                  <Clock className="w-3 h-3 text-[#f1a81f]/70" />
                  <span className="text-white/30 text-[9px] font-black uppercase tracking-widest">ETA</span>
                </div>
                <p className="text-[#f1a81f] font-black text-2xl tabular-nums leading-none">
                  {nextStopEta.toFixed(0)}
                </p>
                <p className="text-white/20 text-[9px] font-bold uppercase mt-0.5">Minutes</p>
              </div>

              {/* Drop-offs */}
              <div className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl p-3 text-center">
                <div className="flex items-center justify-center gap-1.5 mb-1">
                  <Users className="w-3 h-3 text-emerald-400/70" />
                  <span className="text-white/30 text-[9px] font-black uppercase tracking-widest">Drop-offs</span>
                </div>
                <p className="text-emerald-400 font-black text-2xl tabular-nums leading-none">
                  {dropOffsAtNext}
                </p>
                <p className="text-white/20 text-[9px] font-bold uppercase mt-0.5">Passengers</p>
              </div>
            </div>

            {/* Advance stop button */}
            {stops?.length > 0 && currentStopIndex < (stops.length - 2) && (
              <button
                onClick={() => setCurrentStopIndex(prev => prev + 1)}
                className="flex items-center justify-center gap-2 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] rounded-xl py-2.5 px-4 transition-all cursor-pointer"
              >
                <span className="text-white/50 text-[10px] font-black uppercase tracking-wider">Passed Stop</span>
                <ChevronRight className="w-3.5 h-3.5 text-white/30" />
              </button>
            )}
          </div>

          {/* ─── RIGHT BOTTOM: QUICK REPORT BUTTON ─── */}
          <div className="p-4 flex flex-col justify-center gap-3 shrink-0" style={{ minHeight: '40%' }}>

            {reportSent ? (
              /* Success banner */
              <div className="flex-1 flex flex-col items-center justify-center gap-3 bg-emerald-500/10 border border-emerald-500/25 rounded-2xl p-4">
                <div className="w-14 h-14 rounded-full bg-emerald-500/20 flex items-center justify-center">
                  <Zap className="w-7 h-7 text-emerald-400" />
                </div>
                <p className="text-emerald-400 text-xs font-black uppercase tracking-widest text-center">
                  Report Sent to Dispatch
                </p>
                <p className="text-white/30 text-[10px] font-bold uppercase tracking-wider capitalize">
                  {reportSent === 'traffic' ? '🚦 Traffic Jam' : reportSent === 'police' ? '👮 Police Stop' : '🔧 Vehicle Breakdown'}
                </p>
              </div>
            ) : reportModal ? (
              /* Report type selector */
              <div className="flex-1 flex flex-col gap-2">
                <p className="text-white/30 text-[10px] font-black uppercase tracking-widest text-center mb-1">
                  Select Report Type
                </p>
                <button
                  onClick={() => handleReport('traffic')}
                  className="flex-1 flex items-center justify-center gap-3 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 rounded-xl transition-all cursor-pointer"
                >
                  <AlertTriangle className="w-6 h-6 text-amber-400" />
                  <span className="text-amber-400 font-black text-sm uppercase tracking-wider">Traffic Jam</span>
                </button>
                <button
                  onClick={() => handleReport('police')}
                  className="flex-1 flex items-center justify-center gap-3 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 rounded-xl transition-all cursor-pointer"
                >
                  <ShieldAlert className="w-6 h-6 text-blue-400" />
                  <span className="text-blue-400 font-black text-sm uppercase tracking-wider">Police Stop</span>
                </button>
                <button
                  onClick={() => handleReport('breakdown')}
                  className="flex-1 flex items-center justify-center gap-3 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded-xl transition-all cursor-pointer"
                >
                  <Wrench className="w-6 h-6 text-red-400" />
                  <span className="text-red-400 font-black text-sm uppercase tracking-wider">Breakdown</span>
                </button>
                <button
                  onClick={() => setReportModal(null)}
                  className="py-2 text-white/20 text-[10px] font-bold uppercase tracking-widest hover:text-white/40 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            ) : (
              /* Giant touch target */
              <button
                onClick={() => setReportModal(true)}
                className="flex-1 flex flex-col items-center justify-center gap-3 bg-red-600/10 hover:bg-red-600/20 border-2 border-dashed border-red-500/30 hover:border-red-500/50 rounded-2xl transition-all active:scale-[0.97] cursor-pointer min-h-[140px]"
              >
                <div className="w-16 h-16 rounded-full bg-red-500/15 border border-red-500/30 flex items-center justify-center">
                  <AlertTriangle className="w-8 h-8 text-red-400" />
                </div>
                <div className="text-center">
                  <p className="text-red-400 font-black text-sm uppercase tracking-widest">
                    Quick Report
                  </p>
                  <p className="text-white/20 text-[10px] font-bold uppercase tracking-wider mt-0.5">
                    Tap to alert dispatch
                  </p>
                </div>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
