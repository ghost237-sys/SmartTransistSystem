import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

// --- Helper: Fetch live fleet data ---
const fetchFleetLocations = async () => {
  const { data } = await axios.get("/api/fleet/tracking/live/");
  return data;
};

// --- Helper: Fetch Analytics ---
const fetchFleetAnalytics = async () => {
  const { data } = await axios.get("/api/fleet/analytics/");
  return data;
};

export default function FleetDashboard() {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const markersRef = useRef({}); // Store markers to avoid re-rendering the whole map
  const [selectedBus, setSelectedBus] = useState(null);

  // Poll live locations every 5 seconds
  const { data: liveBuses = [] } = useQuery({
    queryKey: ["fleetLocations"],
    queryFn: fetchFleetLocations,
    refetchInterval: 5000, // 5 seconds
  });

  // Fetch analytics (poll slower, e.g., every 60 seconds)
  const { data: analytics } = useQuery({
    queryKey: ["fleetAnalytics"],
    queryFn: fetchFleetAnalytics,
    refetchInterval: 60000,
  });

  // Initialize Map
  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json", // Free Map tiles
      center: [36.8172, -1.2864], // Default center (e.g., Nairobi)
      zoom: 12,
    });

    map.current.addControl(new maplibregl.NavigationControl(), "top-right");
  }, []);

  // Update Markers when liveBuses data changes
  useEffect(() => {
    if (!map.current || !liveBuses) return;

    liveBuses.forEach((bus) => {
      const lngLat = [bus.longitude, bus.latitude];

      if (markersRef.current[bus.bus_id]) {
        // Update existing marker position smoothly
        markersRef.current[bus.bus_id].setLngLat(lngLat);
      } else {
        // Create a new HTML element for the bus marker
        const el = document.createElement("div");
        el.className = "bus-marker";
        el.style.backgroundImage = `url(/bus-icon.png)`; // Add a bus icon to your public folder
        el.style.width = "32px";
        el.style.height = "32px";
        el.style.backgroundSize = "cover";
        el.style.cursor = "pointer";

        const marker = new maplibregl.Marker(el)
          .setLngLat(lngLat)
          .setPopup(
            new maplibregl.Popup({ offset: 25 }).setHTML(
              `<h3 class="font-bold">${bus.plate}</h3><p>Route: ${bus.route}</p><p>Speed: ${bus.speed} km/h</p>`
            )
          )
          .addTo(map.current);

        el.addEventListener("click", () => setSelectedBus(bus));
        markersRef.current[bus.bus_id] = marker;
      }
    });

    // Optional: Remove markers for buses that are no longer active
    const activeIds = liveBuses.map((b) => b.bus_id);
    Object.keys(markersRef.current).forEach((id) => {
      if (!activeIds.includes(id)) {
        markersRef.current[id].remove();
        delete markersRef.current[id];
      }
    });
  }, [liveBuses]);

  return (
    <div className="flex h-screen w-full bg-gray-50">
      {/* Left Sidebar: Analytics & Bus List */}
      <aside className="w-96 bg-white p-6 shadow-lg flex flex-col overflow-y-auto">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">Fleet Dashboard</h1>

        {/* Analytics Cards */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-100">
            <p className="text-sm text-blue-600">Active Buses</p>
            <p className="text-2xl font-bold text-blue-900">
              {analytics?.active_buses ?? "..."}
            </p>
          </div>
          <div className="bg-green-50 p-4 rounded-lg border border-green-100">
            <p className="text-sm text-green-600">Total Trips Today</p>
            <p className="text-2xl font-bold text-green-900">
              {analytics?.total_trips ?? "..."}
            </p>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-100">
            <p className="text-sm text-yellow-600">Revenue</p>
            <p className="text-2xl font-bold text-yellow-900">
              KES {analytics?.revenue ?? "..."}
            </p>
          </div>
          <div className="bg-red-50 p-4 rounded-lg border border-red-100">
            <p className="text-sm text-red-600">Delayed</p>
            <p className="text-2xl font-bold text-red-900">
              {analytics?.delayed_buses ?? "..."}
            </p>
          </div>
        </div>

        {/* Bus List */}
        <h2 className="text-lg font-semibold mb-3">Live Vehicles</h2>
        <div className="flex flex-col gap-2 flex-grow">
          {liveBuses.map((bus) => (
            <div
              key={bus.bus_id}
              onClick={() => {
                setSelectedBus(bus);
                map.current.flyTo({
                  center: [bus.longitude, bus.latitude],
                  zoom: 15,
                });
              }}
              className={`p-3 border rounded-md cursor-pointer hover:bg-gray-50 ${
                selectedBus?.bus_id === bus.bus_id ? "border-blue-500 bg-blue-50" : ""
              }`}
            >
              <div className="flex justify-between items-center">
                <span className="font-medium">{bus.plate}</span>
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    bus.status === "moving"
                      ? "bg-green-100 text-green-800"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  {bus.status}
                </span>
              </div>
              <p className="text-sm text-gray-500">{bus.route}</p>
            </div>
          ))}
        </div>
      </aside>

      {/* Right Side: Live Map */}
      <main className="flex-grow relative">
        <div ref={mapContainer} className="absolute inset-0" />
      </main>
    </div>
  );
}