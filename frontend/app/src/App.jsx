import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import { RequireAuth } from './auth/RequireAuth'

import LoginPage from './pages/LoginPage'
import UnauthorizedPage from './pages/UnauthorizedPage'

// Commuter pages
import CommuterLayout from './layouts/CommuterLayout'
import TripSearchPage from './pages/commuter/TripSearchPage'
import BookingPage from './pages/commuter/BookingPage'
import TrackingPage from './pages/commuter/TrackingPage'
import MyTicketsPage from './pages/commuter/MyTicketsPage'
import ParcelTrackingPage from './pages/commuter/ParcelTrackingPage'



// Fleet owner pages
import FleetLayout from './layouts/FleetLayout'
import DashboardPage from './pages/fleet/DashboardPage'
import LiveMapPage from './pages/fleet/LiveMapPage'
import AnalyticsPage from './pages/fleet/AnalyticsPage'
import ParcelsPage from './pages/fleet/ParcelsPage'
import FleetDashboard from "./pages/fleet/FleetDashboard";


// Conductor pages
import ConductorLayout from './layouts/ConductorLayout'
import ManifestPage from './pages/conductor/ManifestPage'
import ScanPage from './pages/conductor/ScanPage'
import CashPage from './pages/conductor/CashPage'

// Driver pages
import DriverLayout from './layouts/DriverLayout'
import TripsPage from './pages/driver/TripsPage'
import NavigatePage from './pages/driver/NavigatePage'

// Register page
import RegisterPage from './pages/RegisterPage'




function RoleRedirect() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  const routes = {
    commuter: '/commuter',
    fleet_owner: '/fleet',
    conductor: '/conductor',
    driver: '/driver',
    super_admin: '/fleet',
  }
  return <Navigate to={routes[user.role] || '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/unauthorized" element={<UnauthorizedPage />} />
      <Route path="/" element={<RoleRedirect />} />

      {/* Commuter routes */}
      <Route path="/commuter" element={
        <RequireAuth roles={['commuter']}>
          <CommuterLayout />
        </RequireAuth>
      }>
        <Route index element={<TripSearchPage />} />
        <Route path="book/:tripId" element={<BookingPage />} />
        <Route path="track/:tripId" element={<TrackingPage />} />
        <Route path="tickets" element={<MyTicketsPage />} />
        <Route path="parcels" element={<ParcelTrackingPage />} />
      </Route>

      {/* Fleet owner routes */}
      <Route path="/fleet" element={
        <RequireAuth roles={['fleet_owner', 'super_admin']}>
          <FleetLayout />
        </RequireAuth>
      }>
        <Route index element={<DashboardPage />} />
        <Route path="live" element={<LiveMapPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="parcels" element={<ParcelsPage />} />
        <Route path="dashboard" element={<FleetDashboard />} />
      </Route>

      {/* Conductor routes */}
      <Route path="/conductor" element={
        <RequireAuth roles={['conductor']}>
          <ConductorLayout />
        </RequireAuth>
      }>
        <Route index element={<ManifestPage />} />
        <Route path="scan" element={<ScanPage />} />
        <Route path="cash" element={<CashPage />} />
      </Route>

      {/* Driver routes */}
      <Route path="/driver" element={
        <RequireAuth roles={['driver']}>
          <DriverLayout />
        </RequireAuth>
      }>
        <Route index element={<TripsPage />} />
        <Route path="trip/:tripId" element={<NavigatePage />} />
      </Route>
    </Routes>
  )
}