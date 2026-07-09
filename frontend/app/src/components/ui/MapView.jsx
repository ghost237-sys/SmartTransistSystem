import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY

function createStopMarkerElement(stop, index, total, isPickup = false) {
  const isFirst = index === 0
  const isLast = index === total - 1

  const wrapper = document.createElement('div')
  wrapper.style.cssText = `
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: pointer;
    transform: translateY(-4px);
  `

  const dot = document.createElement('div')
  dot.style.cssText = `
    width: ${isPickup ? '18px' : isFirst || isLast ? '14px' : '10px'};
    height: ${isPickup ? '18px' : isFirst || isLast ? '14px' : '10px'};
    border-radius: 50%;
    background: ${isPickup ? '#2563eb' : isFirst ? '#4ade80' : isLast ? '#F5A623' : '#1B4332'};
    border: ${isPickup ? '3px solid #93c5fd' : '2px solid white'};
    box-shadow: 0 2px 6px rgba(0,0,0,0.35);
    flex-shrink: 0;
    ${isPickup ? 'animation: pulse 1.5s ease-in-out infinite;' : ''}
  `

  const label = document.createElement('div')
  label.textContent = stop.name
  label.title = stop.name
  label.style.cssText = `
    margin-top: 4px;
    font-family: Inter, system-ui, sans-serif;
    font-size: 10px;
    font-weight: 600;
    line-height: 1.2;
    color: #2D2D2D;
    background: rgba(255, 255, 255, 0.95);
    padding: 2px 6px;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.25);
    white-space: nowrap;
    max-width: 110px;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: center;
    pointer-events: none;
  `

  wrapper.appendChild(dot)
  wrapper.appendChild(label)
  return wrapper
}

export default function MapView({
  stops = [],
  vehiclePosition = null,
  routePath = null,
  pickupStop = null,
  height = '400px',
  className = '',
}) {
  const mapContainer = useRef(null)
  const mapRef = useRef(null)
  const [mapReady, setMapReady] = useState(false)
  const vehicleMarkerRef = useRef(null)
  const markersRef = useRef([])

  // Initialize map once
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_KEY}`,
      center: [36.9281, -1.2092],
      zoom: 10,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => setMapReady(true))

    mapRef.current = map

    return () => {
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []
      vehicleMarkerRef.current = null
      setMapReady(false)
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Draw / update route line
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    if (!routePath || routePath.length < 2) return

    const routeData = {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: routePath },
    }

    if (map.getSource('route')) {
      map.getSource('route').setData(routeData)
    } else {
      map.addSource('route', { type: 'geojson', data: routeData })
      map.addLayer({
        id: 'route-line',
        type: 'line',
        source: 'route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': '#1B4332',
          'line-width': 4,
          'line-opacity': 0.8,
        },
      })
    }

    const bounds = routePath.reduce(
      (b, coord) => b.extend(coord),
      new maplibregl.LngLatBounds(routePath[0], routePath[0]),
    )
    map.fitBounds(bounds, { padding: 60 })
  }, [routePath, mapReady])

  // Draw / update stop markers with visible labels
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return

    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    stops.forEach((stop, index) => {
      const isPickup = pickupStop && stop.id === pickupStop.id
      const el = createStopMarkerElement(stop, index, stops.length, isPickup)

      const popup = new maplibregl.Popup({
        offset: 20,
        closeButton: false,
        className: 'stop-popup',
      }).setHTML(`
        <div style="font-family: Inter, sans-serif; padding: 4px 2px;">
          <p style="font-weight: 600; font-size: 13px; margin: 0; color: #2D2D2D;">${stop.name}</p>
          <p style="font-size: 11px; color: #5A5A5A; margin: 2px 0 0;">Stop ${index + 1} of ${stops.length}</p>
        </div>
      `)

      const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
        .setLngLat([stop.longitude, stop.latitude])
        .setPopup(popup)
        .addTo(map)

      markersRef.current.push(marker)
    })
  }, [stops, mapReady, pickupStop])

  // Update vehicle position
  useEffect(() => {
    const map = mapRef.current
    if (!map || !vehiclePosition) return

    const { latitude, longitude } = vehiclePosition

    if (vehicleMarkerRef.current) {
      vehicleMarkerRef.current.setLngLat([longitude, latitude])
    } else {
      const el = document.createElement('div')
      el.innerHTML = '🚌'
      el.style.cssText = `
        font-size: 24px;
        cursor: pointer;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.4));
        transition: transform 0.3s ease;
      `

      vehicleMarkerRef.current = new maplibregl.Marker({ element: el })
        .setLngLat([longitude, latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 25, closeButton: false })
            .setHTML(`<p style="font-weight:600;font-size:13px;margin:0">Live position</p>`),
        )
        .addTo(map)
    }
  }, [vehiclePosition])

  return (
    <div
      ref={mapContainer}
      style={{ height }}
      className={`rounded-xl overflow-hidden ${className}`}
    />
  )
}
