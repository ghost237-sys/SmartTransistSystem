import { useState, useEffect } from 'react'
import { passesApi } from '../../api/passes'
import { getRoutes } from '../../api/routes'
import QRCode from 'react-qr-code'
import { 
  Calendar, 
  Clock, 
  MapPin, 
  ShieldCheck, 
  Sparkles, 
  Award,
  Info 
} from 'lucide-react'

export default function MyCommuterPassPage() {
  const [activePass, setActivePass] = useState(null)
  const [availableTiers, setAvailableTiers] = useState([])
  const [creditScore, setCreditScore] = useState(null)
  const [routes, setRoutes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // View 1: Configuration & Purchase States
  const [selectedRouteId, setSelectedRouteId] = useState('')
  const [passType, setPassType] = useState('weekly') // 'weekly' or 'monthly'
  const [seatPreference, setSeatPreference] = useState('window') // 'window', 'aisle', 'any'
  const [purchaseLoading, setPurchaseLoading] = useState(false)

  // View 2: Active Pass States
  const [reservedSlot, setReservedSlot] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Load routes first to resolve names
      let routesList = []
      try {
        routesList = await getRoutes()
        setRoutes(routesList)
        if (routesList.length > 0) {
          setSelectedRouteId(routesList[0].id)
        }
      } catch (e) {
        console.error('Error loading routes:', e)
      }

      // Load active pass
      try {
        const myPassResponse = await passesApi.getMyPass()
        if (myPassResponse.data && myPassResponse.data.id) {
          const pass = myPassResponse.data
          const savedRouteId = localStorage.getItem('commuter_pass_route_id')
          const savedSeatPref = localStorage.getItem('commuter_pass_seat_preference')
          const selectedRoute = routesList.find(r => r.id === savedRouteId)

          pass.route_name = selectedRoute ? selectedRoute.name : 'Ngong - Nairobi CBD'
          pass.seat_preference = savedSeatPref || 'window'
          setActivePass(pass)
        } else {
          setActivePass(null)
        }
      } catch (passErr) {
        if (passErr.response?.status === 404) {
          setActivePass(null)
        } else {
          console.error('Error loading active pass:', passErr)
        }
      }
      
      // Load available tiers
      const tiersResponse = await passesApi.getTiers()
      setAvailableTiers(tiersResponse.data.results || tiersResponse.data)
      
      // Load credit score
      try {
        const creditResponse = await passesApi.getCreditScore()
        setCreditScore(creditResponse.data)
      } catch (e) {
        console.log('No credit score yet')
      }
    } catch (err) {
      console.error('Error loading pass data:', err)
      setError('Failed to load pass data')
    } finally {
      setLoading(false)
    }
  }

  const handlePurchase = async () => {
    if (!selectedRouteId) {
      setError('Please select a route destination.')
      return
    }

    const targetTier = availableTiers.find(t => t.tier_type === passType)
    if (!targetTier) {
      setError('No matching pass tier found in database.')
      return
    }

    try {
      setError(null)
      setPurchaseLoading(true)
      
      // Create pass in backend database
      await passesApi.createPass({ 
        tier: targetTier.id, 
        auto_renew: false 
      })
      
      // Cache preferences locally for demo presentation
      localStorage.setItem('commuter_pass_route_id', selectedRouteId)
      localStorage.setItem('commuter_pass_seat_preference', seatPreference)
      
      await loadData()
    } catch (err) {
      console.error('Error purchasing pass:', err)
      setError(err.response?.data?.detail || 'Failed to purchase pass. Please try again.')
    } finally {
      setPurchaseLoading(false)
    }
  }

  const handleCancelPass = async () => {
    if (!activePass) return
    if (!window.confirm('Are you sure you want to cancel this pass?')) return
    
    try {
      setError(null)
      await passesApi.cancelPass(activePass.id)
      localStorage.removeItem('commuter_pass_route_id')
      localStorage.removeItem('commuter_pass_seat_preference')
      setReservedSlot(null)
      await loadData()
    } catch (err) {
      console.error('Error cancelling pass:', err)
      setError('Failed to cancel pass')
    }
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-KE', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <svg className="animate-spin h-8 w-8 text-[#143d2c]" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      </div>
    )
  }

  return (
    <div className="w-full">
      {activePass ? (
        /* View 2: Active Pass & "Check-In" Management State */
        <div className="flex flex-col gap-6 pb-24">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
              Active Commuter Pass
            </h1>
            <button
              onClick={handleCancelPass}
              className="text-xs font-bold text-red-600 border border-red-200 bg-red-50 hover:bg-red-100 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
            >
              Cancel Pass
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl">
              {error}
            </div>
          )}

          {/* Scannable Digital Asset Card */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">
            {/* Card Header (Deep Forest Green Background) */}
            <div className="bg-[#143d2c] text-white p-5 flex justify-between items-start">
              <div>
                <span className="text-[10px] bg-[#f1a81f] text-[#143d2c] font-black px-2 py-0.5 rounded-full uppercase tracking-wider">
                  {activePass.tier_details?.name || 'Commuter Pass'}
                </span>
                <h2 className="text-xl font-bold mt-2" style={{ fontFamily: 'serif' }}>
                  {activePass.route_name || 'Daily Transit Route'}
                </h2>
                <p className="text-xs text-white/70 mt-1 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  Valid until: {formatDate(activePass.end_date)}
                </p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-black text-[#f1a81f]">
                  {activePass.trips_remaining ?? activePass.tier_details?.trip_allowance}
                </p>
                <p className="text-[10px] text-white/70 font-bold uppercase tracking-wider">
                  Trips Left
                </p>
              </div>
            </div>

            {/* Verification QR Code Area */}
            <div className="p-6 flex flex-col items-center justify-center gap-6 border-b border-gray-100">
              <div className="bg-white p-4 border border-gray-200 rounded-2xl shadow-inner flex items-center justify-center">
                <QRCode
                  value={JSON.stringify({
                    pass_id: activePass.id,
                    commuter: user?.username || 'commuter',
                    route: activePass.route_name || 'Route',
                    seatPreference: activePass.seat_preference || 'No Preference',
                    status: reservedSlot ? 'RESERVED' : 'STANDBY',
                    reservedTime: reservedSlot || 'N/A',
                    timestamp: new Date().toISOString()
                  })}
                  size={170}
                  level="H"
                  style={{ height: "auto", maxWidth: "100%", width: "100%" }}
                />
              </div>

              <div className="text-center">
                <p className="text-xs font-bold text-ink uppercase tracking-wide flex items-center justify-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-green-600" />
                  Conductor Scan Verified
                </p>
                <p className="text-[11px] text-ink-light mt-1">
                  Present this QR code to the conductor during boarding.
                </p>
              </div>
            </div>

            {/* Dynamic Status Indicator Banners */}
            {reservedSlot ? (
              /* Reserved State Card */
              <div className="bg-amber-50 border-t-2 border-b-2 border-[#f1a81f]/70 p-5 flex justify-between items-center transition-all">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-[#f1a81f]/20 flex items-center justify-center font-bold text-lg text-amber-950 shrink-0">
                    🎫
                  </div>
                  <div>
                    <p className="text-xs font-extrabold text-amber-900 uppercase tracking-wider">
                      Status: Reserved Seat
                    </p>
                    <p className="text-sm font-bold text-ink mt-0.5">
                      Guaranteed seat at {reservedSlot} today
                    </p>
                    <p className="text-[10px] text-amber-800 mt-0.5">
                      Preference: <span className="capitalize">{activePass.seat_preference}</span> seat secured
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setReservedSlot(null)}
                  className="text-xs font-bold bg-amber-200/50 hover:bg-amber-200/80 border border-amber-300 text-amber-950 px-3 py-2 rounded-xl transition-all cursor-pointer"
                >
                  Cancel Seat
                </button>
              </div>
            ) : (
              /* Standby State Card */
              <div className="bg-emerald-50/50 border-t border-b border-emerald-100 p-5 flex justify-between items-center transition-all">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center font-bold text-lg text-emerald-800 shrink-0">
                    🚌
                  </div>
                  <div>
                    <p className="text-xs font-extrabold text-emerald-800 uppercase tracking-wider">
                      Status: Standby Passenger
                    </p>
                    <p className="text-xs text-emerald-955 mt-1 leading-relaxed">
                      Board any active bus on standby, or reserve an upcoming departure slot below.
                    </p>
                  </div>
                </div>
                <span className="text-[10px] font-bold bg-emerald-800 text-white px-2.5 py-1 rounded-full uppercase tracking-wider">
                  Standby
                </span>
              </div>
            )}

            {/* Time Slot Picker */}
            <div className="p-6 bg-gray-50/50">
              <label className="text-xs font-bold text-ink-light uppercase tracking-wider flex items-center gap-1.5 mb-4">
                <Clock className="w-3.5 h-3.5 text-[#143d2c]" />
                Reserve a Seat Time Slot (Today)
              </label>
              
              <div className="grid grid-cols-3 gap-2.5">
                {[
                  '06:30 AM',
                  '07:15 AM',
                  '08:00 AM',
                  '08:45 AM',
                  '05:30 PM',
                  '06:15 PM',
                  '07:00 PM'
                ].map((time) => {
                  const isSelected = reservedSlot === time
                  return (
                    <button
                      key={time}
                      onClick={() => setReservedSlot(time)}
                      className={`py-3 text-[11px] font-bold rounded-xl border text-center transition-all cursor-pointer ${
                        isSelected
                          ? 'border-[#f1a81f] bg-[#f1a81f]/10 text-amber-950 ring-2 ring-[#f1a81f]/30'
                          : 'border-gray-200 hover:border-gray-300 bg-white text-ink'
                      }`}
                    >
                      {time}
                    </button>
                  )
                })}
              </div>

              <div className="mt-4 bg-white rounded-xl p-3 border border-gray-100 flex items-start gap-2.5">
                <Info className="w-4 h-4 text-[#143d2c] shrink-0 mt-0.5" />
                <p className="text-[10px] text-ink-light leading-relaxed">
                  Reserving a seat locks your spot on that specific departure. If you do not board within 5 minutes before departure, your reservation lapses and reverts to standby.
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* View 1: Configuration & Purchase State */
        <div className="flex flex-col gap-6 pb-24">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
              Commuter Subscription
            </h1>
            {creditScore && (
              <div className="bg-white border border-gray-200 rounded-xl px-4 py-1.5 shadow-sm">
                <span className="text-xs text-ink-light">Credit Score:</span>
                <span className="ml-2 font-bold text-green-700">{creditScore.score}/100</span>
              </div>
            )}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl">
              {error}
            </div>
          )}

          {/* Setup Form */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6 flex flex-col gap-6 shadow-sm">
            
            {/* Step 1: Fixed Route Destination */}
            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-ink-light uppercase tracking-wider flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-[#143d2c]" />
                1. Select Route Destination
              </label>
              <select
                value={selectedRouteId}
                onChange={(e) => setSelectedRouteId(e.target.value)}
                className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-ink font-medium focus:border-[#143d2c] focus:ring-2 focus:ring-emerald-50 outline-none transition-all"
              >
                <option value="" disabled>Choose your daily commute...</option>
                {routes.map((route) => (
                  <option key={route.id} value={route.id}>
                    {route.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Step 2: Duration Toggle */}
            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-ink-light uppercase tracking-wider flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-[#143d2c]" />
                2. Choose Subscription Duration
              </label>
              <div className="grid grid-cols-2 bg-gray-50 border border-gray-200 rounded-xl p-1">
                <button
                  onClick={() => setPassType('weekly')}
                  className={`py-3 text-xs font-bold uppercase tracking-wider rounded-lg transition-all cursor-pointer ${
                    passType === 'weekly' 
                      ? 'bg-[#143d2c] text-white shadow-sm' 
                      : 'text-ink-light hover:text-ink'
                  }`}
                >
                  Weekly Pass
                </button>
                <button
                  onClick={() => setPassType('monthly')}
                  className={`py-3 text-xs font-bold uppercase tracking-wider rounded-lg transition-all cursor-pointer ${
                    passType === 'monthly' 
                      ? 'bg-[#143d2c] text-white shadow-sm' 
                      : 'text-ink-light hover:text-ink'
                  }`}
                >
                  Monthly Pass
                </button>
              </div>
            </div>

            {/* Step 3: Seat preference */}
            <div className="flex flex-col gap-2">
              <label className="text-xs font-bold text-ink-light uppercase tracking-wider flex items-center gap-1.5">
                <Award className="w-3.5 h-3.5 text-[#143d2c]" />
                3. Seat Tier Preference
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'window', label: 'Window' },
                  { id: 'aisle', label: 'Aisle' },
                  { id: 'any', label: 'Any Seat' }
                ].map(pref => (
                  <button
                    key={pref.id}
                    onClick={() => setSeatPreference(pref.id)}
                    className={`py-3 text-xs font-bold rounded-xl border text-center transition-all cursor-pointer ${
                      seatPreference === pref.id
                        ? 'border-[#143d2c] bg-emerald-50 text-[#143d2c] ring-2 ring-emerald-50'
                        : 'border-gray-200 hover:border-gray-300 text-ink'
                    }`}
                  >
                    {pref.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="h-px bg-gray-100 my-1" />

            {/* Dynamic Pricing Summary Card */}
            <div className="bg-emerald-50/50 border border-emerald-100/80 rounded-2xl p-5 flex flex-col gap-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-bold text-emerald-800 uppercase tracking-wider">Dynamic Pricing Summary</p>
                  <h4 className="font-bold text-ink text-base mt-1" style={{ fontFamily: 'serif' }}>
                    {passType === 'weekly' ? 'Weekly Season Pass' : 'Monthly Season Pass'}
                  </h4>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-black text-[#143d2c]">
                    {passType === 'weekly' ? 'KES 950' : 'KES 3,872'}
                  </p>
                  <p className="text-[10px] text-emerald-800 font-bold uppercase tracking-wide mt-0.5">
                    {passType === 'weekly' ? '10 Trips Allowance' : '44 Trips Allowance'}
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-2 text-xs text-emerald-955 font-semibold bg-white/60 rounded-xl p-3 border border-emerald-100/50">
                <div className="flex justify-between">
                  <span>Duration Validity</span>
                  <span className="font-bold text-[#143d2c]">{passType === 'weekly' ? '7 Days' : '30 Days'}</span>
                </div>
                <div className="flex justify-between">
                  <span>Standard Cost (KES 100/trip)</span>
                  <span className="line-through text-gray-400">
                    {passType === 'weekly' ? 'KES 1,000' : 'KES 4,400'}
                  </span>
                </div>
                <div className="flex justify-between text-green-700">
                  <span>Discount Applied</span>
                  <span className="font-bold">{passType === 'weekly' ? '5% Off' : '12% Off'}</span>
                </div>
                <div className="h-px bg-emerald-100/55 my-1" />
                <div className="flex justify-between font-bold text-[#143d2c]">
                  <span>Seat Preference</span>
                  <span className="capitalize">{seatPreference} seat</span>
                </div>
              </div>
            </div>

            {/* Purchase Button */}
            <button
              onClick={handlePurchase}
              disabled={purchaseLoading || !selectedRouteId}
              className={`w-full text-white font-bold py-4 rounded-xl transition-all shadow-md flex items-center justify-center gap-2 cursor-pointer ${
                purchaseLoading || !selectedRouteId
                  ? 'bg-gray-300 cursor-not-allowed shadow-none'
                  : 'bg-[#143d2c] hover:bg-emerald-950 hover:shadow-lg'
              }`}
            >
              {purchaseLoading ? (
                <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              ) : (
                <>
                  <Sparkles className="w-5 h-5 text-[#f1a81f]" />
                  <span>Purchase Commuter Pass</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
