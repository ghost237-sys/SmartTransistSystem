import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../../auth/AuthContext'
import { findRide, getNearbyRoutes, getStops, findLinkedJourney } from '../../api/trips'
import { formatBusLabel } from '../../utils/busLabel'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import SmartDropdown from '../../components/ui/SmartDropdown'

export default function RideSearchPage() {
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
  const [isTwoWay, setIsTwoWay] = useState(false)
  const [isLink, setIsLink] = useState(false)
  const [returnDestinationSearch, setReturnDestinationSearch] = useState('')
  const [selectedReturnStop, setSelectedReturnStop] = useState(null)
  const [selectedReturnStopId, setSelectedReturnStopId] = useState(null)
  const [finalDestinationSearch, setFinalDestinationSearch] = useState('')
  const [selectedFinalStop, setSelectedFinalStop] = useState(null)
  const [selectedFinalStopId, setSelectedFinalStopId] = useState(null)

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

  const { data: nearbyBuses, isLoading: loadingNearbyBuses } = useQuery({
    queryKey: ['nearby-buses', pickupLocation?.lat, pickupLocation?.lng],
    queryFn: async () => {
      if (!pickupLocation) return []
      const res = await findRide(pickupLocation.lat, pickupLocation.lng)
      return res.data
    },
    enabled: !!pickupLocation,
    refetchInterval: 30000,
  })

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
      // Use complete route data to maintain correct sequence
      route.allStops.forEach((stop) => {
        if (!stopsMap.has(stop.id)) {
          stopsMap.set(stop.id,({
            id: stop.id,
            name: stop.name,
            routeId: route.id,
            routeName: route.name,
            sequence: stop.sequence,
            // Store complete route data for return journey
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
    
    // Get the sequence of selected stop
    const selectedSequence = selectedStop.sequence
    
    // Get all stops with sequence less than selected stop (stops before it in route)
    const stopsBefore = selectedStop.completeStopIds
      .map((id, index) => ({
        id: id,
        name: selectedStop.completeStops[index],
        sequence: selectedStop.completeSequences[index],
        routeId: selectedStop.routeId,
        routeName: selectedStop.routeName
      }))
      .filter(stop => stop.sequence < selectedSequence)
    
    // Sort by sequence in descending order for return journey
    stopsBefore.sort((a, b) => b.sequence - a.sequence)
    
    return stopsBefore
  }, [selectedStopId, allAvailableStops])

  const filteredStops = useMemo(() => {
    if (!destinationSearch) return allAvailableStops
    const search = destinationSearch.toLowerCase()
    return allAvailableStops.filter(stop =>
      stop.name.toLowerCase().includes(search)
    )
  }, [destinationSearch, allAvailableStops])

  const { data: rides, isLoading, error } = useQuery({
    queryKey: ['find-ride', pickupLocation?.lat, pickupLocation?.lng, selectedStopId],
    queryFn: async () => {
      if (!pickupLocation || !selectedStopId) return []
      // For Two Way, require return destination as well
      if (isTwoWay && !selectedReturnStopId) return []
      const res = await findRide(pickupLocation.lat, pickupLocation.lng, selectedStopId)
      return res.data
    },
    enabled: !!pickupLocation && !!selectedStopId && (!isTwoWay || !!selectedReturnStopId) && !isLink,
  })

  const { data: linkedJourneys, isLoading: loadingLinked, error: linkedError } = useQuery({
    queryKey: ['find-linked-journey', pickupLocation?.lat, pickupLocation?.lng, selectedFinalStopId],
    queryFn: async () => {
      if (!pickupLocation || !selectedFinalStopId) return []
      const res = await findLinkedJourney(pickupLocation.lat, pickupLocation.lng, selectedFinalStopId)
      return res.data
    },
    enabled: !!pickupLocation && !!selectedFinalStopId && isLink,
  })

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

  const handleBookRide = (ride) => {
    navigate(`/commuter/book/${ride.trip_id}`, {
      state: {
        pickupStopId: useCurrentLocation ? ride.pickup_stop_id : selectedPickupStopId,
        pickupStopName: useCurrentLocation ? ride.pickup_stop_name : selectedPickupStop?.name,
        alightingStopId: selectedStopId,
        alightingStopName: selectedStop,
        etaMinutes: ride.eta_minutes,
        isTwoWay,
        returnDestinationId: selectedReturnStopId,
        returnDestinationName: selectedReturnStop,
      },
    })
  }


  return (
    <div className="flex flex-col min-h-screen">
      {/* Header - top third */}
      <div className="flex-shrink-0 pb-4">
        <h1 className="text-2xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
          Find a Ride
        </h1>
        <p className="text-ink-light text-sm mt-1">
          Find buses near you, pick where to alight, and book your seat.
        </p>
      </div>

      {/* Main content - lower two-thirds for thumb zone */}
      <div className="flex-1 flex flex-col gap-4">
        <Card className="flex flex-col gap-4">
          {/* Trip type toggles */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setIsTwoWay(false)
                setIsLink(false)
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                !isTwoWay && !isLink
                  ? 'bg-green-deep text-white'
                  : 'bg-gray-100 text-ink-light hover:bg-gray-200'
              }`}
            >
              One Way
            </button>
            <button
              onClick={() => {
                setIsTwoWay(true)
                setIsLink(false)
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isTwoWay
                  ? 'bg-green-deep text-white'
                  : 'bg-gray-100 text-ink-light hover:bg-gray-200'
              }`}
            >
              Two Way
            </button>
            <button
              onClick={() => {
                setIsLink(true)
                setIsTwoWay(false)
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isLink
                  ? 'bg-green-deep text-white'
                  : 'bg-gray-100 text-ink-light hover:bg-gray-200'
              }`}
            >
              Link
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
              placeholder="Select pickup stage"
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

          {/* Where to */}
          {allAvailableStops.length > 0 && !isLink && (
            <div>
              <label className="block text-sm font-medium text-ink mb-2">
                {isTwoWay ? 'First destination?' : 'Where to?'}
              </label>
              <SmartDropdown
                placeholder="Search destination"
                value={destinationSearch}
                onChange={setDestinationSearch}
                items={filteredStops}
                renderItem={(item) => (
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-pale border-2 border-green-mid flex items-center justify-center text-xs font-medium text-green-deep">
                      {item.index}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-ink">{item.name}</p>
                      <p className="text-xs text-ink-light mt-1">{item.routeName}</p>
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
                loading={loadingRoutes}
              />
            </div>
          )}

          {/* Final destination for Link mode */}
          {isLink && allAvailableStops.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-ink mb-2">Final destination?</label>
              <SmartDropdown
                placeholder="Search final destination"
                value={finalDestinationSearch}
                onChange={setFinalDestinationSearch}
                items={filteredStops}
                renderItem={(item) => (
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-purple-pale border-2 border-purple-mid flex items-center justify-center text-xs font-medium text-purple-deep">
                      {item.index}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-ink">{item.name}</p>
                      <p className="text-xs text-ink-light mt-1">{item.routeName}</p>
                    </div>
                    {selectedFinalStopId === item.id && (
                      <svg className="w-5 h-5 text-purple-deep" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    )}
                  </div>
                )}
                onSelect={(item) => {
                  handleFinalStopSelect(item.name, item.id)
                }}
                emptyMessage="No stops found"
                loading={loadingRoutes}
              />
            </div>
          )}

          {/* Return destination for Two Way */}
          {isTwoWay && selectedStop && (
            <div>
              <label className="block text-sm font-medium text-ink mb-2">Return destination?</label>
              <SmartDropdown
                placeholder="Search return destination"
                value={returnDestinationSearch}
                onChange={setReturnDestinationSearch}
                items={returnStops.filter(stop => 
                  stop.name.toLowerCase().includes(returnDestinationSearch.toLowerCase())
                )}
                renderItem={(item) => (
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-pale border-2 border-blue-mid flex items-center justify-center text-xs font-medium text-blue-deep">
                      {item.index}
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

          {/* No routes message */}
          {pickupLocation && !loadingRoutes && routeList.length === 0 && (
            <div className="text-center py-4">
              <p className="text-ink-light text-sm">No buses serve {useCurrentLocation ? 'your location' : selectedPickupStop?.name} right now.</p>
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
          {!isLoading && !error && rides && rides.length === 0 && pickupLocation && selectedStop && !isLink && (
            <div className="text-center py-8">
              <p className="text-ink-light">No buses available within 1 hour on your route.</p>
              <p className="text-xs text-ink-light mt-1">
                We'll notify you when a bus becomes available.
              </p>
            </div>
          )}

          {/* No linked journeys */}
          {!loadingLinked && !linkedError && linkedJourneys && linkedJourneys.length === 0 && pickupLocation && selectedFinalStop && isLink && (
            <div className="text-center py-8">
              <p className="text-ink-light">No linked journeys available to {selectedFinalStop}.</p>
              <p className="text-xs text-ink-light mt-1">
                Try searching for a direct route instead.
              </p>
            </div>
          )}

          {/* Rides list (One Way / Two Way) */}
          {!isLoading && !error && rides && rides.length > 0 && !isLink && (
            <div className="flex flex-col gap-3">
              <p className="text-sm font-medium text-ink">
                {rides.length} bus{rides.length > 1 ? 'es' : ''} {useCurrentLocation ? 'near you' : 'near ' + selectedPickupStop?.name} going to {selectedStop}
              </p>
              {rides.map((ride) => (
                <div key={ride.trip_id} className={`border rounded-xl p-4 transition-colors ${showRefreshBanner ? 'animate-pulse border-amber-300' : 'border-gray-200 hover:border-green-mid'}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-semibold text-ink">{formatBusLabel(ride)}</span>
                        <Badge variant="green">Active</Badge>
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
                      <Button
                        size="sm"
                        disabled={ride.available_seats === 0}
                        onClick={() => handleBookRide(ride)}
                      >
                        {ride.available_seats > 0 ? 'Book' : 'Full'}
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Linked Journeys list (Link mode) */}
          {!loadingLinked && !linkedError && linkedJourneys && linkedJourneys.length > 0 && isLink && (
            <div className="flex flex-col gap-3">
              <p className="text-sm font-medium text-ink">
                {linkedJourneys.length} linked journey{linkedJourneys.length > 1 ? 's' : ''} to {selectedFinalStop}
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
                      onClick={() => {
                        // Navigate to linked booking flow (to be implemented)
                        navigate(`/commuter/book/${journey.first_leg.trip_id}`, {
                          state: {
                            isLinkedJourney: true,
                            linkedRouteId: journey.linked_route_id,
                            firstLeg: journey.first_leg,
                            secondLeg: journey.second_leg,
                            transferStationName: journey.transfer_station_name,
                            totalFare: journey.total_fare,
                            pickupStopId: useCurrentLocation ? journey.first_leg.pickup_stop_id : selectedPickupStopId,
                            pickupStopName: useCurrentLocation ? journey.first_leg.pickup_stop_name : selectedPickupStop?.name,
                          },
                        })
                      }}
                    >
                      {journey.first_leg.available_seats > 0 && journey.second_leg.available_seats > 0 ? 'Book Linked Journey' : 'Not Available'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

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
      </div>
    </div>
  )
}
