import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../../auth/AuthContext'
import { findRide, getNearbyRoutes, getStops, findLinkedJourney } from '../../api/trips'
import { createMultiModeBooking } from '../../api/bookings'
import { formatBusLabel } from '../../utils/busLabel'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import SmartDropdown from '../../components/ui/SmartDropdown'
import { SUPER_METRO_ROUTES, getAllOtherStops, inferDirection, getIntermediateStops, matchRouteKey } from '../../utils/routeStages'

export default function BookingSearchPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [userLocation, setUserLocation] = useState(null)
  const [locationLabel, setLocationLabel] = useState(null)
  const [locationError, setLocationError] = useState(null)
  const [pickupSearch, setPickupSearch] = useState('')
  const [selectedPickupStop, setSelectedPickupStop] = useState(null)
  const [selectedPickupStopId, setSelectedPickupStopId] = useState(null)
  const [useCurrentLocation, setUseCurrentLocation] = useState(true)
  const [destinationSearch, setDestinationSearch] = useState('')
  const [selectedStop, setSelectedStop] = useState(null)
  const [selectedStopId, setSelectedStopId] = useState(null)
  const [showRefreshBanner, setShowRefreshBanner] = useState(false)
  const [inactiveTime, setInactiveTime] = useState(0)
  
  // Trip mode state
  const [tripMode, setTripMode] = useState('single') // 'single', 'return', 'link'
  // Direction is auto-inferred from boarding→destination sequence (no manual toggle)
  const [isReturn, setIsReturn] = useState(false)
  const [returnTime, setReturnTime] = useState('')
  const [returnDestinationSearch, setReturnDestinationSearch] = useState('')
  const [selectedReturnStop, setSelectedReturnStop] = useState(null)
  const [selectedReturnStopId, setSelectedReturnStopId] = useState(null)
  const [finalDestinationSearch, setFinalDestinationSearch] = useState('')
  const [selectedFinalStop, setSelectedFinalStop] = useState(null)
  const [selectedFinalStopId, setSelectedFinalStopId] = useState(null)
  const [selectedOutboundTrip, setSelectedOutboundTrip] = useState(null)
  const [selectedReturnTrip, setSelectedReturnTrip] = useState(null)
  
  // Auto-detect route type
  const [hasDirectRoute, setHasDirectRoute] = useState(null)
  const [hasLinkedRoute, setHasLinkedRoute] = useState(null)

  // Resolve location: demo preset for demo users, else browser geolocation
  useEffect(() => {
    if (user?.demoLat != null && user?.demoLng != null) {
      setUserLocation({ lat: user.demoLat, lng: user.demoLng })
      setLocationLabel(user.demoLocationLabel || 'Demo location')
      return undefined
    }

    if (!navigator.geolocation) {
      setLocationError('Geolocation is not supported. Log in as a demo commuter or enable location.')
      return undefined
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setUserLocation({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        })
        setLocationLabel('Your location')
      },
      () => {
        setLocationError('Could not get your location. Log in as commuter_alice, commuter_bob, or commuter_carol for demo.')
      }
    )
    return undefined
  }, [user?.demoLat, user?.demoLng, user?.demoLocationLabel])

  // Reset timer on user interaction
  useEffect(() => {
    const handleInteraction = () => {
      setInactiveTime(0)
      setShowRefreshBanner(false)
    }

    window.addEventListener('click', handleInteraction)
    window.addEventListener('touchstart', handleInteraction)
    window.addEventListener('keydown', handleInteraction)

    return () => {
      window.removeEventListener('click', handleInteraction)
      window.removeEventListener('touchstart', handleInteraction)
      window.removeEventListener('keydown', handleInteraction)
    }
  }, [])

  const { data: allStops } = useQuery({
    queryKey: ['all-stops'],
    queryFn: async () => {
      const res = await getStops()
      return res.data
    },
  })

  const pickupLocation = useCurrentLocation ? userLocation : selectedPickupStop

  const { data: nearbyRoutes, isLoading: loadingRoutes } = useQuery({
    queryKey: ['nearby-routes', pickupLocation?.lat, pickupLocation?.lng],
    queryFn: async () => {
      if (!pickupLocation) return []
      const res = await getNearbyRoutes(pickupLocation.lat, pickupLocation.lng)
      return res.data
    },
    enabled: !!pickupLocation,
  })

  const routeList = useMemo(() => {
    if (!nearbyRoutes) return []
    return nearbyRoutes.map(route => ({
      id: route.route_id,
      name: route.route_name,
      nearestStopName: route.nearest_stop_name,
      nearestStopSequence: route.nearest_stop_sequence,
      distanceKm: route.distance_km,
      stops: route.stops
        .filter(s => s.sequence > route.nearest_stop_sequence)
        .map(s => s.name),
      stopIds: route.stops
        .filter(s => s.sequence > route.nearest_stop_sequence)
        .map(s => s.id),
      allStops: route.stops,
    }))
  }, [nearbyRoutes])

  // Extract all available stops from all routes
  const allAvailableStops = useMemo(() => {
    if (!routeList) return []
    const stopsMap = new Map()
    routeList.forEach(route => {
      route.allStops.forEach((stop) => {
        if (!stopsMap.has(stop.id)) {
          stopsMap.set(stop.id,({
            id: stop.id,
            name: stop.name,
            routeId: route.id,
            routeName: route.name,
            sequence: stop.sequence,
            completeStops: route.allStops.map(s => s.name),
            completeStopIds: route.allStops.map(s => s.id),
            completeSequences: route.allStops.map(s => s.sequence)
          }))
        }
      })
    })
    return Array.from(stopsMap.values())
  }, [routeList])

  // Get return stops in reverse order from the selected destination's route
  const returnStops = useMemo(() => {
    if (!selectedStopId || !allAvailableStops.length) return []
    
    const selectedStop = allAvailableStops.find(stop => stop.id === selectedStopId)
    if (!selectedStop) return []
    
    const selectedSequence = selectedStop.sequence
    
    const stopsBefore = selectedStop.completeStopIds
      .map((id, index) => ({
        id: id,
        name: selectedStop.completeStops[index],
        sequence: selectedStop.completeSequences[index],
        routeId: selectedStop.routeId,
        routeName: selectedStop.routeName
      }))
      .filter(stop => stop.sequence < selectedSequence)
    
    stopsBefore.sort((a, b) => b.sequence - a.sequence)
    
    return stopsBefore
  }, [selectedStopId, allAvailableStops])

  // Auto-infer direction from boarding→destination sequence
  const inferredDirection = useMemo(() => {
    if (!selectedStop || !routeList?.length) return null
    const boardingStageName = !useCurrentLocation && selectedPickupStop
      ? selectedPickupStop.name
      : routeList?.[0]?.nearestStopName || null
    if (!boardingStageName) return null

    for (const route of routeList) {
      const key = matchRouteKey(route.name)
      if (key) {
        const dir = inferDirection(key, boardingStageName, selectedStop)
        if (dir) return dir
      }
    }
    return null
  }, [selectedStop, routeList, useCurrentLocation, selectedPickupStop])

  // Auto-compute intermediate stops for the route summary
  const intermediateStops = useMemo(() => {
    if (!selectedStop || !routeList?.length) return []
    const boardingStageName = !useCurrentLocation && selectedPickupStop
      ? selectedPickupStop.name
      : routeList?.[0]?.nearestStopName || null
    if (!boardingStageName) return []

    for (const route of routeList) {
      const key = matchRouteKey(route.name)
      if (key) {
        const stops = getIntermediateStops(key, boardingStageName, selectedStop)
        if (stops.length > 0) return stops
      }
    }
    return []
  }, [selectedStop, routeList, useCurrentLocation, selectedPickupStop])

  const filteredStops = useMemo(() => {
    const stopsSource = tripMode === 'link' ? (allStops || []) : allAvailableStops
    
    // Deduplicate by name to prevent duplicate keys and clean up dropdown list
    const uniqueStops = []
    const seenNames = new Set()
    for (const stop of stopsSource) {
      if (!seenNames.has(stop.name)) {
        seenNames.add(stop.name)
        uniqueStops.push(stop)
      }
    }

    // Show all other stops on matching routes (both directions)
    // so mid-route commuters can pick either way
    let routeFiltered = uniqueStops
    if (tripMode !== 'link') {
      const boardingStageName = !useCurrentLocation && selectedPickupStop
        ? selectedPickupStop.name
        : routeList?.[0]?.nearestStopName || null

      if (boardingStageName) {
        const matchedRouteKeys = []
        for (const route of routeList || []) {
          const key = matchRouteKey(route.name)
          if (key && !matchedRouteKeys.includes(key)) matchedRouteKeys.push(key)
        }

        if (matchedRouteKeys.length > 0) {
          const allowedDestinations = new Set()
          for (const routeKey of matchedRouteKeys) {
            // Show ALL other stops, not just downstream — direction is auto-detected after selection
            const otherStops = getAllOtherStops(routeKey, boardingStageName)
            otherStops.forEach(name => allowedDestinations.add(name))
          }

          if (allowedDestinations.size > 0) {
            const matched = uniqueStops.filter(stop => allowedDestinations.has(stop.name))
            // Only apply the filter if it actually matched some backend stops;
            // otherwise fall back to showing all stops (name mismatch between
            // hardcoded route data and backend stop names)
            if (matched.length > 0) {
              routeFiltered = matched
            }
          }
        }
      }
    }

    if (!destinationSearch) return routeFiltered
    const search = destinationSearch.toLowerCase()
    return routeFiltered.filter(stop =>
      stop.name.toLowerCase().includes(search)
    )
  }, [destinationSearch, allAvailableStops, allStops, tripMode, useCurrentLocation, selectedPickupStop, routeList])

  // Query for direct routes
  const { data: rides, isLoading, error } = useQuery({
    queryKey: ['find-ride', pickupLocation?.lat, pickupLocation?.lng, selectedStopId],
    queryFn: async () => {
      if (!pickupLocation || !selectedStopId) return []
      const res = await findRide(pickupLocation.lat, pickupLocation.lng, selectedStopId)
      return res.data
    },
    enabled: !!pickupLocation && !!selectedStopId && tripMode !== 'link',
  })

  // Query for linked routes
  const { data: linkedJourneys, isLoading: loadingLinked, error: linkedError } = useQuery({
    queryKey: ['find-linked-journey', pickupLocation?.lat, pickupLocation?.lng, selectedFinalStopId],
    queryFn: async () => {
      if (!pickupLocation || !selectedFinalStopId) return []
      const res = await findLinkedJourney(pickupLocation.lat, pickupLocation.lng, selectedFinalStopId)
      return res.data
    },
    enabled: !!pickupLocation && !!selectedFinalStopId && tripMode === 'link',
  })

  // Query for return routes
  const { data: returnRides, isLoading: loadingReturnRides } = useQuery({
    queryKey: ['find-return-ride', selectedStopId, selectedPickupStopId],
    queryFn: async () => {
      if (!selectedStopId || !selectedPickupStopId) return []
      const destStop = allStops?.find(s => s.id === selectedStopId)
      if (!destStop) return []
      const res = await findRide(destStop.latitude, destStop.longitude, selectedPickupStopId)
      return res.data
    },
    enabled: !!selectedStopId && !!selectedPickupStopId && tripMode === 'return',
  })

  // Reset selected trips when parameters change
  useEffect(() => {
    setSelectedOutboundTrip(null)
    setSelectedReturnTrip(null)
  }, [selectedStopId, selectedPickupStopId, tripMode])

  // Auto-detect route availability when destination is selected
  useEffect(() => {
    if (selectedStopId && pickupLocation) {
      // Check for direct routes
      findRide(pickupLocation.lat, pickupLocation.lng, selectedStopId)
        .then(res => {
          const hasDirect = res.data && res.data.length > 0
          setHasDirectRoute(hasDirect)
          
          if (!hasDirect) {
            // No direct route, check for linked routes
            findLinkedJourney(pickupLocation.lat, pickupLocation.lng, selectedStopId)
              .then(linkedRes => {
                const hasLinked = linkedRes.data && linkedRes.data.length > 0
                setHasLinkedRoute(hasLinked)
                
                if (hasLinked) {
                  // Auto-switch to link mode ONLY if user is currently in single mode
                  if (tripMode === 'single') {
                    setTripMode('link')
                    setSelectedFinalStop(selectedStop)
                    setSelectedFinalStopId(selectedStopId)
                  }
                }
              })
          } else {
            setHasLinkedRoute(false)
            // If user was in link mode but direct is available, default to single
            if (tripMode === 'link') {
              setTripMode('single')
            }
          }
        })
    }
  }, [selectedStopId, pickupLocation])

  // 45-second inactivity timer for seat availability refresh
  useEffect(() => {
    if (!rides || rides.length === 0) {
      setInactiveTime(0)
      setShowRefreshBanner(false)
      return undefined
    }

    const timer = setInterval(() => {
      setInactiveTime(prev => {
        const newTime = prev + 1
        if (newTime >= 45) {
          setShowRefreshBanner(true)
        }
        return newTime
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [rides])

  const handlePickupSelect = (stop) => {
    setSelectedPickupStop(stop)
    setSelectedPickupStopId(stop.id)
    setPickupSearch(stop.name)
    setUseCurrentLocation(false)
  }

  const handleUseCurrentLocation = () => {
    setUseCurrentLocation(true)
    setSelectedPickupStop(null)
    setSelectedPickupStopId(null)
    setPickupSearch('')
  }

  const handleStopSelect = (stopName, stopId) => {
    setSelectedStop(stopName)
    setSelectedStopId(stopId)
    setDestinationSearch(stopName)
    
    // Also sync final stop variables for linked trip search
    setSelectedFinalStop(stopName)
    setSelectedFinalStopId(stopId)
    setFinalDestinationSearch(stopName)

    // Reset route detection
    setHasDirectRoute(null)
    setHasLinkedRoute(null)
  }

  const handleReturnStopSelect = (stopName, stopId) => {
    setSelectedReturnStop(stopName)
    setSelectedReturnStopId(stopId)
    setReturnDestinationSearch(stopName)
  }

  const handleFinalStopSelect = (stopName, stopId) => {
    setSelectedFinalStop(stopName)
    setSelectedFinalStopId(stopId)
    setFinalDestinationSearch(stopName)
  }

  const handleTripModeChange = (mode) => {
    setTripMode(mode)
    if (mode === 'single') {
      setIsReturn(false)
    } else if (mode === 'return') {
      setIsReturn(true)
    } else if (mode === 'link') {
      setIsReturn(false)
    }
  }

  const handleBookRide = (outboundRide) => {
    const bookingData = {
      trip_mode: 'single',
      trip_id: outboundRide.trip_id,
      boarding_stop_id: useCurrentLocation ? outboundRide.pickup_stop_id : selectedPickupStopId,
      alighting_stop_id: selectedStopId,
    }

    navigate(`/commuter/pay/${outboundRide.trip_id}`, {
      state: {
        bookingData,
        pickupStopName: useCurrentLocation ? outboundRide.pickup_stop_name : selectedPickupStop?.name,
        alightingStopName: selectedStop,
        totalFare: Number(outboundRide.fare),
        etaMinutes: outboundRide.eta_minutes,
      }
    })
  }

  const handleBookReturnJourney = () => {
    if (!selectedOutboundTrip || !selectedReturnTrip) return

    const bookingData = {
      trip_mode: 'return_immediate',
      outbound_trip_id: selectedOutboundTrip.trip_id,
      outbound_boarding_stop_id: useCurrentLocation ? selectedOutboundTrip.pickup_stop_id : selectedPickupStopId,
      outbound_alighting_stop_id: selectedStopId,
      return_trip_id: selectedReturnTrip.trip_id,
      return_boarding_stop_id: selectedStopId,
      return_alighting_stop_id: useCurrentLocation ? selectedOutboundTrip.pickup_stop_id : selectedPickupStopId,
    }

    // Departure time from return trip
    const depTime = selectedReturnTrip.departure_time 
      ? new Date(selectedReturnTrip.departure_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : 'scheduled time'

    navigate(`/commuter/pay/${selectedOutboundTrip.trip_id}`, {
      state: {
        bookingData,
        pickupStopName: useCurrentLocation ? selectedOutboundTrip.pickup_stop_name : selectedPickupStop?.name,
        alightingStopName: selectedStop,
        totalFare: Number(selectedOutboundTrip.fare) + Number(selectedReturnTrip.fare),
        etaMinutes: selectedOutboundTrip.eta_minutes,
        isTwoWay: true,
        returnTime: depTime,
      }
    })
  }

  const handleBookLinkedJourney = (journey) => {
    const bookingData = {
      trip_mode: 'linked',
      first_leg_trip_id: journey.first_leg.trip_id,
      first_leg_boarding_stop_id: useCurrentLocation ? journey.first_leg.pickup_stop_id : selectedPickupStopId,
      first_leg_alighting_stop_id: journey.first_leg.transfer_stop_id,
      second_leg_trip_id: journey.second_leg.trip_id,
      second_leg_boarding_stop_id: journey.second_leg.pickup_stop_id,
      second_leg_alighting_stop_id: selectedFinalStopId,
      transfer_station_id: journey.linked_route_id,
    }

    navigate(`/commuter/pay/${journey.first_leg.trip_id}`, {
      state: {
        bookingData,
        isLinkedJourney: true,
        linkedRouteId: journey.linked_route_id,
        firstLeg: journey.first_leg,
        secondLeg: journey.second_leg,
        transferStationName: journey.transfer_station_name,
        totalFare: journey.total_fare,
        pickupStopId: useCurrentLocation ? journey.first_leg.pickup_stop_id : selectedPickupStopId,
        pickupStopName: useCurrentLocation ? journey.first_leg.pickup_stop_name : selectedPickupStop?.name,
        alightingStopName: selectedFinalStop,
        etaMinutes: journey.first_leg.eta_minutes,
      },
    })
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <div className="flex-shrink-0 pb-4">
        <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
          Book Your Ride
        </h1>
        <p className="text-ink-light text-sm mt-1">
          Select your destination and we'll find the best route for you.
        </p>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col gap-4">
        <Card className="flex flex-col gap-4">
          {/* Trip Type Segmented Control */}
          <div className="bg-gray-100 p-1.5 rounded-2xl flex w-full">
            <button
              type="button"
              onClick={() => handleTripModeChange('single')}
              className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-bold transition-all duration-200 ${
                tripMode === 'single'
                  ? 'bg-green-deep text-white shadow-md'
                  : 'text-ink-light hover:text-ink'
              }`}
            >
              One Way
            </button>
            <button
              type="button"
              onClick={() => handleTripModeChange('return')}
              className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-bold transition-all duration-200 ${
                tripMode === 'return'
                  ? 'bg-green-deep text-white shadow-md'
                  : 'text-ink-light hover:text-ink'
              }`}
            >
              Two Way (Return)
            </button>
            <button
              type="button"
              onClick={() => handleTripModeChange('link')}
              className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-bold transition-all duration-200 ${
                tripMode === 'link'
                  ? 'bg-green-deep text-white shadow-md'
                  : 'text-ink-light hover:text-ink'
              }`}
            >
              Link Trip
            </button>
          </div>

          {/* Location status */}
          <div className="flex items-center gap-3 text-sm">
            {userLocation ? (
              <>
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-ink font-medium">{locationLabel}</span>
                {userLocation && (
                  <button
                    onClick={handleUseCurrentLocation}
                    className={`text-xs ml-auto ${useCurrentLocation ? 'text-green-mid font-medium' : 'text-ink-light hover:text-green-mid'}`}
                  >
                    {useCurrentLocation ? 'Using current location' : 'Use current location'}
                  </button>
                )}
              </>
            ) : locationError ? (
              <>
                <div className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-red-600">{locationError}</span>
              </>
            ) : (
              <>
                <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                <span className="text-ink-light">Detecting your location...</span>
              </>
            )}
          </div>

          {/* Where from */}
          <div>
            <label className="block text-sm font-medium text-ink mb-2">Where from?</label>
            <SmartDropdown
              placeholder="Select pickup location"
              value={pickupSearch}
              onChange={setPickupSearch}
              items={allStops?.filter(stop => {
                const matchesSearch = stop.name.toLowerCase().includes(pickupSearch.toLowerCase())
                if (!userLocation) return matchesSearch
                const distance = Math.sqrt(
                  Math.pow(stop.latitude - userLocation.lat, 2) +
                  Math.pow(stop.longitude - userLocation.lng, 2)
                )
                const distanceKm = distance * 111
                return matchesSearch && distanceKm <= 5
              }).map(stop => ({
                id: stop.id,
                name: stop.name,
                lat: stop.latitude,
                lng: stop.longitude,
              })) || []}
              renderItem={(item) => (
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-ink">{item.name}</p>
                    <p className="text-xs text-ink-light mt-1">
                      {item.lat.toFixed(4)}, {item.lng.toFixed(4)}
                    </p>
                  </div>
                  {selectedPickupStopId === item.id && (
                    <svg className="w-5 h-5 text-green-deep" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  )}
                </div>
              )}
              onSelect={handlePickupSelect}
              emptyMessage={userLocation ? "No nearby stops found" : "Enable location to see nearby stops"}
              loading={!allStops}
            />
          </div>

          {/* Destination selector */}
          {((tripMode === 'link' && allStops && allStops.length > 0) || allAvailableStops.length > 0) && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-ink">Where to?</label>
                {inferredDirection && (
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                    inferredDirection === 'outbound'
                      ? 'bg-green-50 text-green-700 border border-green-200'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      inferredDirection === 'outbound' ? 'bg-green-500' : 'bg-amber-500'
                    }`} />
                    {inferredDirection === 'outbound' ? 'Outbound' : 'Inbound'}
                  </span>
                )}
              </div>
              <SmartDropdown
                placeholder="Search destination"
                value={destinationSearch}
                onChange={setDestinationSearch}
                items={filteredStops}
                renderItem={(item) => (
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-pale border-2 border-green-mid flex items-center justify-center text-xs font-medium text-green-deep">
                      {item.sequence}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-ink">{item.name}</p>
                      <p className="text-xs text-ink-light mt-1">{item.routeName || item.route_name}</p>
                    </div>
                    {selectedStopId === item.id && (
                      <svg className="w-5 h-5 text-green-deep" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    )}
                  </div>
                )}
                onSelect={(item) => {
                  handleStopSelect(item.name, item.id)
                }}
                emptyMessage="No stops found"
                loading={tripMode === 'link' ? !allStops : loadingRoutes}
              />
            </div>
          )}

          {/* Route detection indicator */}
          {selectedStopId && (hasDirectRoute !== null || hasLinkedRoute !== null) && (
            <div className={`rounded-xl p-3 ${hasDirectRoute ? 'bg-green-50 border border-green-200' : hasLinkedRoute ? 'bg-purple-50 border border-purple-200' : 'bg-amber-50 border border-amber-200'}`}>
              {hasDirectRoute ? (
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-sm text-green-800 font-medium">Direct route available</span>
                </div>
              ) : hasLinkedRoute ? (
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                  <span className="text-sm text-purple-800 font-medium">Transfer route available - auto-selected</span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span className="text-sm text-amber-800 font-medium">No routes available to this destination</span>
                </div>
              )}
            </div>
          )}

          {/* Route recommendation card */}
          {selectedStopId && hasDirectRoute === false && hasLinkedRoute === true && tripMode !== 'link' && (
            <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 flex flex-col gap-2">
              <p className="text-sm font-medium text-purple-900">
                No direct buses found for this trip, but a transfer connection is available.
              </p>
              <Button
                size="sm"
                className="bg-purple-600 hover:bg-purple-700 text-white w-full py-2.5"
                onClick={() => handleTripModeChange('link')}
              >
                Switch to Link Trip
              </Button>
            </div>
          )}

          {/* Return time picker - only show for return mode */}
          {tripMode === 'return' && selectedStop && (
            <div>
              <label className="block text-sm font-medium text-ink mb-2">Return time</label>
              <input
                type="time"
                value={returnTime}
                onChange={(e) => setReturnTime(e.target.value)}
                className="w-full px-4 py-3 rounded-lg border border-gray-200 focus:border-green-mid focus:ring-2 focus:ring-green-pale outline-none transition-all"
              />
              <p className="text-xs text-ink-light mt-1">Select your preferred return time</p>
            </div>
          )}

          {/* Return destination for return mode */}
          {tripMode === 'return' && selectedStop && (
            <div>
              <label className="block text-sm font-medium text-ink mb-2">Return to?</label>
              <SmartDropdown
                placeholder="Select return destination"
                value={returnDestinationSearch}
                onChange={setReturnDestinationSearch}
                items={returnStops.filter(stop => 
                  stop.name.toLowerCase().includes(returnDestinationSearch.toLowerCase())
                )}
                renderItem={(item) => (
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-pale border-2 border-blue-mid flex items-center justify-center text-xs font-medium text-blue-deep">
                      {item.sequence}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-ink">{item.name}</p>
                      <p className="text-xs text-ink-light mt-1">{item.routeName}</p>
                    </div>
                    {selectedReturnStopId === item.id && (
                      <svg className="w-5 h-5 text-blue-deep" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    )}
                  </div>
                )}
                onSelect={(item) => {
                  handleReturnStopSelect(item.name, item.id)
                }}
                emptyMessage="No return stops available"
                loading={loadingRoutes}
              />
            </div>
          )}

          {/* Linked journey info - only show for link mode */}
          {tripMode === 'link' && selectedFinalStop && (
            <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
              <div className="flex items-start gap-3">
                <svg className="w-6 h-6 text-purple-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                <div className="flex-1">
                  <h4 className="font-semibold text-purple-900 mb-1">Transfer Required</h4>
                  <p className="text-sm text-purple-700 mb-2">
                    Your destination requires a transfer. We'll book both legs of your journey automatically.
                  </p>
                  <div className="bg-white rounded-lg p-3 border border-purple-100">
                    <p className="text-xs text-purple-600 font-medium mb-1">How it works:</p>
                    <ul className="text-xs text-purple-700 space-y-1">
                      <li className="flex items-start gap-2">
                        <span className="text-purple-500">•</span>
                        <span>Board the first bus to the transfer station</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-purple-500">•</span>
                        <span>Your second seat locks automatically as you approach the transfer point</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-purple-500">•</span>
                        <span>Transfer to the second bus for the final leg</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Loading */}
          {(isLoading || loadingLinked) && (
            <div className="flex justify-center py-8">
              <svg className="animate-spin h-6 w-6 text-green-deep" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            </div>
          )}

          {/* Error */}
          {(error || linkedError) && (
            <div className="border-red-100 bg-red-50 rounded-xl px-4 py-3">
              <p className="text-red-600 text-sm">Failed to find rides. Please try again.</p>
            </div>
          )}

          {/* No rides */}
          {!isLoading && !error && rides && rides.length === 0 && pickupLocation && selectedStop && tripMode !== 'link' && hasDirectRoute === false && (
            <div className="text-center py-8">
              <p className="text-ink-light">No direct buses available to {selectedStop}.</p>
              {hasLinkedRoute && (
                <p className="text-xs text-ink-light mt-1">
                  A transfer route is available - see linked journeys below.
                </p>
              )}
            </div>
          )}

          {/* Direct rides list (Single or Outbound leg of Return) */}
          {!isLoading && !error && rides && rides.length > 0 && tripMode !== 'link' && (
            <div className="flex flex-col gap-4">
              <div>
                <p className="text-sm font-bold text-ink uppercase tracking-wider mb-2">
                  {tripMode === 'return' ? '1. Select Outbound Commute' : 'Available Commutes'}
                </p>
                <p className="text-xs text-ink-light mb-3">
                  {rides.length} bus{rides.length > 1 ? 'es' : ''} {useCurrentLocation ? 'near you' : 'near ' + selectedPickupStop?.name} going to {selectedStop}
                </p>
              </div>

              <div className="flex flex-col gap-3">
                {rides.map((ride) => {
                  const isSelected = selectedOutboundTrip?.trip_id === ride.trip_id;
                  return (
                    <div
                      key={ride.trip_id}
                      className={`border rounded-xl p-4 transition-all duration-200 ${
                        isSelected
                          ? 'border-green-deep border-2 bg-green-50/20 shadow-sm'
                          : 'border-gray-200 hover:border-green-mid bg-white'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="font-semibold text-ink">{formatBusLabel(ride)}</span>
                            <Badge variant="green">Active</Badge>
                            {isSelected && (
                              <span className="bg-green-deep text-white text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                                ✓ Outbound Selected
                              </span>
                            )}
                          </div>
                          <div className="text-sm text-ink-light">{ride.route_name}</div>
                          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                            <div>
                              <span className="text-ink-light">ETA: </span>
                              <span className="font-medium text-ink">{ride.eta_minutes} min</span>
                            </div>
                            <div>
                              <span className="text-ink-light">Seats: </span>
                              <span className={`font-medium ${ride.available_seats > 0 ? 'text-green-mid' : 'text-red-500'}`}>
                                {ride.available_seats}
                              </span>
                            </div>
                            <div>
                              <span className="text-ink-light">Pickup: </span>
                              <span className="font-medium text-ink">{ride.pickup_stop_name}</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-2 shrink-0">
                          <div className="text-lg font-bold text-ink">
                            KES {Number(ride.fare).toLocaleString()}
                          </div>
                          {tripMode === 'return' ? (
                            <Button
                              size="sm"
                              variant={isSelected ? 'secondary' : 'primary'}
                              disabled={ride.available_seats === 0}
                              onClick={() => setSelectedOutboundTrip(isSelected ? null : ride)}
                            >
                              {isSelected ? 'Change' : 'Select Outbound'}
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              disabled={ride.available_seats === 0}
                              onClick={() => handleBookRide(ride)}
                            >
                              {ride.available_seats > 0 ? 'Book' : 'Full'}
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Return Commute section (Only if outbound is chosen) */}
              {tripMode === 'return' && selectedOutboundTrip && (
                <div className="border-t border-gray-100 pt-6 mt-2 flex flex-col gap-4">
                  <div>
                    <p className="text-sm font-bold text-ink uppercase tracking-wider mb-2">
                      2. Select Return Commute
                    </p>
                    <p className="text-xs text-ink-light mb-3">
                      Buses returning from <span className="font-medium text-ink">{selectedStop}</span> back to <span className="font-medium text-ink">{selectedPickupStop?.name || 'your pickup'}</span>
                    </p>
                  </div>

                  {loadingReturnRides ? (
                    <div className="flex justify-center py-4">
                      <svg className="animate-spin h-5 w-5 text-green-deep" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                    </div>
                  ) : returnRides && returnRides.length > 0 ? (
                    <div className="flex flex-col gap-3">
                      {returnRides.map((returnRide) => {
                        const isSelectedReturn = selectedReturnTrip?.trip_id === returnRide.trip_id;
                        return (
                          <div
                            key={returnRide.trip_id}
                            className={`border rounded-xl p-4 transition-all duration-200 ${
                              isSelectedReturn
                                ? 'border-purple-600 border-2 bg-purple-50/20 shadow-sm'
                                : 'border-gray-200 hover:border-purple-mid bg-white'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1 flex-wrap">
                                  <span className="font-semibold text-ink">{formatBusLabel(returnRide)}</span>
                                  <Badge variant="green">Active</Badge>
                                  {isSelectedReturn && (
                                    <span className="bg-purple-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                                      ✓ Return Selected
                                    </span>
                                  )}
                                </div>
                                <div className="text-sm text-ink-light">{returnRide.route_name}</div>
                                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                                  <div>
                                    <span className="text-ink-light">Departure time: </span>
                                    <span className="font-medium text-ink">
                                      {returnRide.departure_time 
                                        ? new Date(returnRide.departure_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                                        : '2h from now'}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-ink-light">Seats: </span>
                                    <span className={`font-medium ${returnRide.available_seats > 0 ? 'text-green-mid' : 'text-red-500'}`}>
                                      {returnRide.available_seats}
                                    </span>
                                  </div>
                                </div>
                              </div>
                              <div className="flex flex-col items-end gap-2 shrink-0">
                                <div className="text-lg font-bold text-ink">
                                  KES {Number(returnRide.fare).toLocaleString()}
                                </div>
                                <Button
                                  size="sm"
                                  variant={isSelectedReturn ? 'secondary' : 'primary'}
                                  disabled={returnRide.available_seats === 0}
                                  onClick={() => setSelectedReturnTrip(isSelectedReturn ? null : returnRide)}
                                  className={!isSelectedReturn ? 'bg-purple-600 hover:bg-purple-700 text-white font-bold' : 'font-bold'}
                                >
                                  {isSelectedReturn ? 'Change' : 'Select Return'}
                                </Button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-center py-4 border border-dashed border-gray-200 rounded-xl bg-gray-50/50">
                      <p className="text-xs text-ink-light">No return buses available on this route currently.</p>
                    </div>
                  )}
                </div>
              )}

              {/* Checkout Summary card for return booking */}
              {tripMode === 'return' && selectedOutboundTrip && selectedReturnTrip && (
                <Card className="border-green-mid bg-green-50/30 border-2 p-4 flex flex-col sm:flex-row items-center justify-between gap-4 mt-2">
                  <div className="text-center sm:text-left">
                    <h4 className="font-bold text-green-950 text-sm">Confirm Return Booking</h4>
                    <p className="text-xs text-green-800 mt-1">
                      Outbound Bus: <span className="font-semibold text-ink">{selectedOutboundTrip.fleet_code}</span> | 
                      Return Bus: <span className="font-semibold text-ink">{selectedReturnTrip.fleet_code}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-base font-bold text-green-deep">
                      KES {(Number(selectedOutboundTrip.fare) + Number(selectedReturnTrip.fare)).toLocaleString()}
                    </span>
                    <Button
                      size="sm"
                      onClick={handleBookReturnJourney}
                      className="bg-green-deep hover:bg-green-mid text-white font-bold"
                    >
                      Book & Pay
                    </Button>
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* Linked journeys list */}
          {!loadingLinked && !linkedError && linkedJourneys && linkedJourneys.length > 0 && (tripMode === 'link' || hasLinkedRoute) && (
            <div className="flex flex-col gap-3">
              <p className="text-sm font-medium text-ink">
                {linkedJourneys.length} linked journey{linkedJourneys.length > 1 ? 's' : ''} to {selectedFinalStop || selectedStop}
              </p>
              {linkedJourneys.map((journey) => (
                <div key={journey.linked_route_id} className="border rounded-xl p-4 transition-colors border-gray-200 hover:border-purple-mid bg-gradient-to-r from-purple-50 to-white">
                  {/* Journey Header */}
                  <div className="flex items-start justify-between gap-4 mb-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant={journey.is_safe_transfer ? 'green' : 'amber'}>
                          {journey.is_safe_transfer ? 'Safe Transfer' : 'Tight Transfer'}
                        </Badge>
                        <span className="text-xs text-ink-light">
                          {journey.transfer_buffer_minutes} min buffer at {journey.transfer_station_name}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-ink-light">Total time:</span>
                        <span className="font-medium text-ink">{Math.round(journey.total_duration_minutes)} min</span>
                      </div>
                    </div>
                    <div className="text-lg font-bold text-ink">
                      KES {Number(journey.total_fare).toLocaleString()}
                    </div>
                  </div>

                  {/* First Leg */}
                  <div className="bg-white rounded-lg p-3 mb-2 border border-gray-100">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-6 h-6 rounded-full bg-green-pale border-2 border-green-mid flex items-center justify-center text-xs font-bold text-green-deep">1</div>
                      <span className="font-semibold text-ink text-sm">{journey.first_leg.route_name}</span>
                      <Badge variant="green" size="sm">Bus 1</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-ink-light">Pickup: </span>
                        <span className="font-medium text-ink">{journey.first_leg.pickup_stop_name}</span>
                      </div>
                      <div>
                        <span className="text-ink-light">ETA: </span>
                        <span className="font-medium text-ink">{journey.first_leg.eta_minutes} min</span>
                      </div>
                      <div>
                        <span className="text-ink-light">Transfer at: </span>
                        <span className="font-medium text-ink">{journey.first_leg.transfer_stop_name}</span>
                      </div>
                      <div>
                        <span className="text-ink-light">Seats: </span>
                        <span className={`font-medium ${journey.first_leg.available_seats > 0 ? 'text-green-mid' : 'text-red-500'}`}>
                          {journey.first_leg.available_seats}
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-ink-light">
                      {formatBusLabel(journey.first_leg)}
                    </div>
                  </div>

                  {/* Transfer Arrow */}
                  <div className="flex items-center justify-center py-1">
                    <svg className="w-6 h-6 text-purple-mid" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                    </svg>
                  </div>

                  {/* Second Leg */}
                  <div className="bg-white rounded-lg p-3 border border-gray-100">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-6 h-6 rounded-full bg-purple-pale border-2 border-purple-mid flex items-center justify-center text-xs font-bold text-purple-deep">2</div>
                      <span className="font-semibold text-ink text-sm">{journey.second_leg.route_name}</span>
                      <Badge variant="purple" size="sm">Bus 2</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-ink-light">Board at: </span>
                        <span className="font-medium text-ink">{journey.second_leg.pickup_stop_name}</span>
                      </div>
                      <div>
                        <span className="text-ink-light">ETA to dest: </span>
                        <span className="font-medium text-ink">{journey.second_leg.eta_minutes} min</span>
                      </div>
                      <div>
                        <span className="text-ink-light">Departure: </span>
                        <span className="font-medium text-ink">
                          {journey.second_leg.departure_time ? new Date(journey.second_leg.departure_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'TBD'}
                        </span>
                      </div>
                      <div>
                        <span className="text-ink-light">Seats: </span>
                        <span className={`font-medium ${journey.second_leg.available_seats > 0 ? 'text-green-mid' : 'text-red-500'}`}>
                          {journey.second_leg.available_seats}
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-ink-light">
                      {formatBusLabel(journey.second_leg)}
                    </div>
                  </div>

                  {/* Book Button */}
                  <div className="mt-3 flex justify-end">
                    <Button
                      size="sm"
                      disabled={journey.first_leg.available_seats === 0 || journey.second_leg.available_seats === 0}
                      onClick={() => handleBookLinkedJourney(journey)}
                    >
                      {journey.first_leg.available_seats > 0 && journey.second_leg.available_seats > 0 ? 'Book Linked Journey' : 'Not Available'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* No linked journeys */}
          {!loadingLinked && !linkedError && linkedJourneys && linkedJourneys.length === 0 && pickupLocation && selectedFinalStopId && tripMode === 'link' && (
            <div className="text-center py-8">
              <p className="text-ink-light">No transfer routes available to {selectedFinalStop}.</p>
            </div>
          )}

          {/* Refresh banner */}
          {showRefreshBanner && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 animate-pulse">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-amber-600 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span className="text-sm text-amber-800 font-medium">Seat availability updated</span>
                </div>
                <button
                  onClick={() => {
                    setInactiveTime(0)
                    setShowRefreshBanner(false)
                  }}
                  className="text-xs text-amber-600 hover:text-amber-800 font-medium"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
