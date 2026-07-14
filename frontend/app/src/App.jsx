import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import { RequireAuth } from './auth/RequireAuth'

import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import UnauthorizedPage from './pages/UnauthorizedPage'

// Commuter pages
import CommuterLayout from './layouts/CommuterLayout'
import BookingSearchPage from './pages/commuter/BookingSearchPage'
import BookingPage from './pages/commuter/BookingPage'
import PaymentPage from './pages/commuter/PaymentPage'
import BookingConfirmedPage from './pages/commuter/BookingConfirmedPage'
import TrackingPage from './pages/commuter/TrackingPage'
import MyTicketsPage from './pages/commuter/MyTicketsPage'
import MyCommuterPassPage from './pages/commuter/MyCommuterPassPage'

// Fleet owner pages
import FleetLayout from './layouts/FleetLayout'
import DashboardPage from './pages/fleet/DashboardPage'
import LiveMapPage from './pages/fleet/LiveMapPage'
import AnalyticsPage from './pages/fleet/AnalyticsPage'
import ParcelsPage from './pages/fleet/ParcelsPage'
import VehiclesPage from './pages/fleet/VehiclesPage'
import DriversPage from './pages/fleet/DriversPage'
import ConductorsPage from './pages/fleet/ConductorsPage'
import RoutesPage from './pages/fleet/RoutesPage'
import PassTiersManagementPage from './pages/fleet/PassTiersManagementPage'

// Conductor pages
import ConductorLayout from './layouts/ConductorLayout'
import ManifestPage from './pages/conductor/ManifestPage'
import ScanPage from './pages/conductor/ScanPage'
import CashPage from './pages/conductor/CashPage'

// Driver pages
import DriverLayout from './layouts/DriverLayout'
import DriverDashboardPage from './pages/driver/DriverDashboardPage'
import TripsPage from './pages/driver/TripsPage'
import NavigatePage from './pages/driver/NavigatePage'
import DriverManifestPage from './pages/driver/DriverManifestPage'

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
        <Route index element={<BookingSearchPage />} />
        <Route path="book/:tripId" element={<BookingPage />} />
        <Route path="pay/:tripId" element={<PaymentPage />} />
        <Route path="booking/:bookingId" element={<BookingConfirmedPage />} />
        <Route path="track/:tripId" element={<TrackingPage />} />
        <Route path="tickets" element={<MyTicketsPage />} />
        <Route path="pass" element={<MyCommuterPassPage />} />
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
        <Route path="vehicles" element={<VehiclesPage />} />
        <Route path="drivers" element={<DriversPage />} />
        <Route path="conductors" element={<ConductorsPage />} />
        <Route path="routes" element={<RoutesPage />} />
        <Route path="passes" element={<PassTiersManagementPage />} />
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
        <Route index element={<DriverDashboardPage />} />
        <Route path="trips" element={<TripsPage />} />
        <Route path="manifest" element={<DriverManifestPage />} />
        <Route path="manifest/:tripId" element={<DriverManifestPage />} />
        <Route path="trip/:tripId" element={<NavigatePage />} />
      </Route>
    </Routes>
  )
}