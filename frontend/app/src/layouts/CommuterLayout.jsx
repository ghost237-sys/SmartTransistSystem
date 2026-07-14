import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { 
  Home, 
  Search, 
  Ticket, 
  Menu, 
  Calendar, 
  Receipt, 
  Settings, 
  HelpCircle, 
  LogOut,
  X 
} from 'lucide-react'

export default function CommuterLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [isMoreOpen, setIsMoreOpen] = useState(false)
  const [activeModal, setActiveModal] = useState(null)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-100 flex justify-center">
      {/* Mobile App Mirror Frame Container */}
      <div className="w-full max-w-2xl bg-cream min-h-screen flex flex-col relative shadow-2xl border-x border-gray-200">
        
        {/* Sticky App Header (Persistent on top of the mobile column) */}
        <header className="bg-[#143d2c] text-white px-4 py-3.5 flex items-center justify-between sticky top-0 z-30 shadow-sm">
          <NavLink to="/commuter/pass" className="flex items-center">
            <span className="font-bold text-lg" style={{ fontFamily: 'serif' }}>
              Smart<span className="text-[#f1a81f]">Transit</span>
            </span>
          </NavLink>
          
          {/* User profile identifier (opens More drawer on click) */}
          <button 
            onClick={() => setIsMoreOpen(true)}
            className="flex items-center gap-2 text-white/80 hover:text-white cursor-pointer bg-emerald-950/40 py-1 px-2.5 rounded-full border border-emerald-800/40"
          >
            <span className="text-xs font-semibold">@{user?.username || 'commuter'}</span>
            <div className="w-6 h-6 rounded-full bg-emerald-800 flex items-center justify-center font-bold text-xs border border-emerald-700">
              {(user?.username?.[0] || 'C').toUpperCase()}
            </div>
          </button>
        </header>

        {/* Scrollable Page Content (gives padding at bottom for the bottom bar) */}
        <main className="flex-1 w-full px-4 pt-6 pb-28 overflow-y-auto">
          <Outlet />
        </main>

        {/* Layer A: Sticky Bottom Navigation Bar (Centered within max-w-2xl container) */}
        <nav 
          className="fixed bottom-0 w-full max-w-2xl bg-[#143d2c] border-t border-emerald-950 shadow-2xl z-40 transition-all"
          style={{ paddingBottom: 'calc(8px + env(safe-area-inset-bottom, 0px))' }}
        >
          <div className="flex justify-around items-center h-16">
            <NavLink
              to="/commuter/pass"
              className={({ isActive }) =>
                `flex flex-col items-center justify-center w-full h-full text-[10px] font-bold uppercase tracking-wider transition-colors ${
                  isActive ? 'text-[#f1a81f]' : 'text-white/60 hover:text-white'
                }`
              }
            >
              <Home className="w-5 h-5 mb-1" />
              <span>Home</span>
            </NavLink>
            
            <NavLink
              to="/commuter"
              end
              className={({ isActive }) =>
                `flex flex-col items-center justify-center w-full h-full text-[10px] font-bold uppercase tracking-wider transition-colors ${
                  isActive ? 'text-[#f1a81f]' : 'text-white/60 hover:text-white'
                }`
              }
            >
              <Search className="w-5 h-5 mb-1" />
              <span>Plan Trip</span>
            </NavLink>

            <NavLink
              to="/commuter/tickets"
              className={({ isActive }) =>
                `flex flex-col items-center justify-center w-full h-full text-[10px] font-bold uppercase tracking-wider transition-colors ${
                  isActive ? 'text-[#f1a81f]' : 'text-white/60 hover:text-white'
                }`
              }
            >
              <Ticket className="w-5 h-5 mb-1" />
              <span>My Tickets</span>
            </NavLink>

            <button
              onClick={() => setIsMoreOpen(true)}
              className={`flex flex-col items-center justify-center w-full h-full text-[10px] font-bold uppercase tracking-wider transition-colors cursor-pointer ${
                isMoreOpen ? 'text-[#f1a81f]' : 'text-white/60 hover:text-white'
              }`}
            >
              <Menu className="w-5 h-5 mb-1" />
              <span>More</span>
            </button>
          </div>
        </nav>

        {/* Layer B: Interactive Bottom Sheet Slide-Up Backdrop */}
        {isMoreOpen && (
          <div 
            className="fixed inset-0 bg-black/60 z-45 transition-opacity duration-300"
            onClick={() => setIsMoreOpen(false)}
          />
        )}

        {/* Layer B: Interactive Bottom Sheet Slide-Up Drawer */}
        <div 
          className={`fixed bottom-0 w-full max-w-2xl bg-white rounded-t-2xl z-50 px-4 pt-4 pb-8 transition-transform duration-300 transform ${
            isMoreOpen ? 'translate-y-0' : 'translate-y-full'
          }`}
          style={{ paddingBottom: 'calc(2rem + env(safe-area-inset-bottom, 0px))' }}
        >
          {/* Pull bar indicator */}
          <div className="w-12 h-1.5 bg-gray-200 rounded-full mx-auto mb-6" />

          {/* Header */}
          <div className="flex items-center justify-between mb-6 px-2">
            <h2 className="text-lg font-bold text-ink" style={{ fontFamily: 'serif' }}>
              <span className="text-[#143d2c]">Smart</span>
              <span className="text-[#f1a81f]">Transit</span> Menu
            </h2>
            <button 
              onClick={() => setIsMoreOpen(false)}
              className="p-1.5 rounded-full bg-gray-100 text-gray-500 hover:bg-gray-200 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Action Items */}
          <div className="flex flex-col gap-1.5">
            <button
              onClick={() => {
                setIsMoreOpen(false)
                setActiveModal('schedules')
              }}
              className="flex items-center gap-4 w-full p-4 hover:bg-gray-50 rounded-xl text-left transition-colors text-ink cursor-pointer"
            >
              <Calendar className="w-5 h-5 text-[#143d2c]" />
              <span className="font-semibold text-sm">Schedules & Line Status</span>
            </button>

            <button
              onClick={() => {
                setIsMoreOpen(false)
                setActiveModal('history')
              }}
              className="flex items-center gap-4 w-full p-4 hover:bg-gray-50 rounded-xl text-left transition-colors text-ink cursor-pointer"
            >
              <Receipt className="w-5 h-5 text-[#143d2c]" />
              <span className="font-semibold text-sm">Transaction History / Receipts</span>
            </button>

            <button
              onClick={() => {
                setIsMoreOpen(false)
                setActiveModal('settings')
              }}
              className="flex items-center gap-4 w-full p-4 hover:bg-gray-50 rounded-xl text-left transition-colors text-ink cursor-pointer"
            >
              <Settings className="w-5 h-5 text-[#143d2c]" />
              <span className="font-semibold text-sm">Account & Payment Settings</span>
            </button>

            <button
              onClick={() => {
                setIsMoreOpen(false)
                setActiveModal('help')
              }}
              className="flex items-center gap-4 w-full p-4 hover:bg-gray-50 rounded-xl text-left transition-colors text-ink cursor-pointer"
            >
              <HelpCircle className="w-5 h-5 text-[#143d2c]" />
              <span className="font-semibold text-sm">Help & Support</span>
            </button>

            <div className="h-px bg-gray-100 my-2" />

            <button
              onClick={() => {
                setIsMoreOpen(false)
                handleLogout()
              }}
              className="flex items-center gap-4 w-full p-4 hover:bg-red-50 rounded-xl text-left transition-colors text-red-600 cursor-pointer"
            >
              <LogOut className="w-5 h-5" />
              <span className="font-semibold text-sm">Sign Out</span>
            </button>
          </div>
        </div>

        {/* Premium Overlay Modals for Low-Frequency Utilities */}
        {activeModal && (
          <div className="fixed inset-0 bg-black/60 z-55 flex items-center justify-center px-4">
            <div className="bg-white rounded-2xl max-w-md w-full overflow-hidden shadow-2xl animate-fade-in border border-gray-100">
              {/* Header */}
              <div className="bg-[#143d2c] text-white px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {activeModal === 'schedules' && <Calendar className="w-5 h-5 text-[#f1a81f]" />}
                  {activeModal === 'history' && <Receipt className="w-5 h-5 text-[#f1a81f]" />}
                  {activeModal === 'settings' && <Settings className="w-5 h-5 text-[#f1a81f]" />}
                  {activeModal === 'help' && <HelpCircle className="w-5 h-5 text-[#f1a81f]" />}
                  <h3 className="font-bold text-base capitalize">
                    {activeModal === 'schedules' && 'Schedules & Line Status'}
                    {activeModal === 'history' && 'Transaction History'}
                    {activeModal === 'settings' && 'Account Settings'}
                    {activeModal === 'help' && 'Help & Support'}
                  </h3>
                </div>
                <button 
                  onClick={() => setActiveModal(null)}
                  className="p-1 rounded-full hover:bg-emerald-950 text-white/80 hover:text-white transition-colors cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Content */}
              <div className="p-6">
                {activeModal === 'schedules' && (
                  <div className="flex flex-col gap-4">
                    <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-3.5 flex items-start gap-3">
                      <span className="w-2.5 h-2.5 rounded-full bg-green-500 mt-1.5 shrink-0" />
                      <div>
                        <p className="font-semibold text-sm text-[#143d2c]">Thika - Nairobi (Super Metro)</p>
                        <p className="text-xs text-ink-light mt-0.5">Frequency: every 5-10 mins. Normal service operating.</p>
                      </div>
                    </div>
                    <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-3.5 flex items-start gap-3">
                      <span className="w-2.5 h-2.5 rounded-full bg-green-500 mt-1.5 shrink-0" />
                      <div>
                        <p className="font-semibold text-sm text-[#143d2c]">Ngong - Nairobi (Super Metro)</p>
                        <p className="text-xs text-ink-light mt-0.5">Frequency: every 15 mins. Normal service operating.</p>
                      </div>
                    </div>
                    <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-3.5 flex items-start gap-3">
                      <span className="w-2.5 h-2.5 rounded-full bg-green-500 mt-1.5 shrink-0" />
                      <div>
                        <p className="font-semibold text-sm text-[#143d2c]">Kikuyu - Nairobi (Super Metro)</p>
                        <p className="text-xs text-ink-light mt-0.5">Frequency: every 15 mins. Normal service operating.</p>
                      </div>
                    </div>
                    <div className="bg-amber-50 border border-amber-100 rounded-xl p-3.5 flex items-start gap-3">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                      <div>
                        <p className="font-semibold text-sm text-amber-900">Eastleigh - CBD (Super Metro)</p>
                        <p className="text-xs text-amber-800 mt-0.5">Frequency: every 15 mins. Heavy traffic delays near CBD (10-15 min delays).</p>
                      </div>
                    </div>
                  </div>
                )}

                {activeModal === 'history' && (
                  <div className="flex flex-col gap-3">
                    <div className="border border-gray-100 rounded-xl p-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                      <div>
                        <p className="font-bold text-sm text-ink">Ngong to Thika (Transfer)</p>
                        <p className="text-xs text-ink-light mt-1">14 Jul 2026, 16:18 | M-Pesa</p>
                      </div>
                      <span className="font-bold text-sm text-green-700">KES 300.00</span>
                    </div>
                    <div className="border border-gray-100 rounded-xl p-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                      <div>
                        <p className="font-bold text-sm text-ink">Thika to Nairobi (Return)</p>
                        <p className="text-xs text-ink-light mt-1">13 Jul 2026, 08:30 | Commuter Pass</p>
                      </div>
                      <span className="font-bold text-sm text-green-700">1 Ride</span>
                    </div>
                    <div className="border border-gray-100 rounded-xl p-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                      <div>
                        <p className="font-bold text-sm text-ink">Nairobi to Kikuyu (One-Way)</p>
                        <p className="text-xs text-ink-light mt-1">11 Jul 2026, 18:15 | M-Pesa</p>
                      </div>
                      <span className="font-bold text-sm text-green-700">KES 150.00</span>
                    </div>
                  </div>
                )}

                {activeModal === 'settings' && (
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-ink-light uppercase">Commuter Account</label>
                      <div className="bg-gray-50 rounded-xl p-3 border border-gray-200 flex items-center justify-between">
                        <div>
                          <p className="font-bold text-sm text-ink">@{user?.username || 'commuter_dennis'}</p>
                          <p className="text-xs text-ink-light mt-0.5">{user?.phoneNumber || '0712345678'}</p>
                        </div>
                        <span className="text-[10px] font-bold bg-[#143d2c] text-white px-2 py-0.5 rounded-full uppercase">Active</span>
                      </div>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-semibold text-ink-light uppercase">Default Payment Details</label>
                      <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
                        <p className="font-bold text-sm text-ink">M-Pesa Express</p>
                        <p className="text-xs text-ink-light mt-0.5">Authorized Number: {user?.phoneNumber || '0712345678'}</p>
                      </div>
                    </div>
                    <button 
                      onClick={() => setActiveModal(null)}
                      className="w-full bg-[#143d2c] text-white font-bold py-3 rounded-xl hover:bg-emerald-950 transition-colors mt-2 cursor-pointer"
                    >
                      Save & Close
                    </button>
                  </div>
                )}

                {activeModal === 'help' && (
                  <div className="flex flex-col gap-4">
                    <p className="text-sm text-ink-light">Need assistance with your ticket, commuter pass, or M-Pesa transaction?</p>
                    
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-3 p-3 border border-gray-100 rounded-xl hover:bg-gray-50">
                        <div className="w-9 h-9 rounded-full bg-emerald-50 flex items-center justify-center text-[#143d2c] font-bold">📞</div>
                        <div>
                          <p className="text-xs text-ink-light">Super Metro Careline</p>
                          <p className="font-bold text-sm text-[#143d2c]">+254 700 123 456</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 p-3 border border-gray-100 rounded-xl hover:bg-gray-50">
                        <div className="w-9 h-9 rounded-full bg-emerald-50 flex items-center justify-center text-[#143d2c] font-bold">💬</div>
                        <div>
                          <p className="text-xs text-ink-light">WhatsApp Support Desk</p>
                          <p className="font-bold text-sm text-[#143d2c]">+254 722 987 654</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 p-3 border border-gray-100 rounded-xl hover:bg-gray-50">
                        <div className="w-9 h-9 rounded-full bg-emerald-50 flex items-center justify-center text-[#143d2c] font-bold">✉️</div>
                        <div>
                          <p className="text-xs text-ink-light">Email Office</p>
                          <p className="font-bold text-sm text-[#143d2c]">support@smarttransit.co.ke</p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-3.5">
                      <p className="font-bold text-xs text-[#143d2c] uppercase">Geofenced Transfers</p>
                      <p className="text-[11px] text-emerald-800 mt-1 leading-relaxed">
                        For link trips, your transfer seat booking is held in a "Pending Bay" and does not occupy a seat. Once your first bus gets within 2.0 km of the transfer hub, the second ticket QR code activates automatically!
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}