import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { getProfileStatus, updateProfile, requestDeviceMigration } from '../../api/auth'

export default function CommuterDashboardHome() {
  const { user, setUser, deviceUuid } = useAuth()
  const navigate = useNavigate()

  // Profile status state
  const [profileData, setProfileData] = useState(null)
  const [loadingProfile, setLoadingProfile] = useState(true)

  // Progressive profile form
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [showProfileForm, setShowProfileForm] = useState(false)
  const [updatingProfile, setUpdatingProfile] = useState(false)
  const [profileSuccessMsg, setProfileSuccessMsg] = useState('')

  // SMS recovery form
  const [recoveryPhone, setRecoveryPhone] = useState('')
  const [sendingRecovery, setSendingRecovery] = useState(false)
  const [recoverySuccessMsg, setRecoverySuccessMsg] = useState('')
  const [recoveryErrorMsg, setRecoveryErrorMsg] = useState('')

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const data = await getProfileStatus()
        setProfileData(data)
      } catch (err) {
        console.error("Error fetching commuter profile:", err)
      } finally {
        setLoadingProfile(false)
      }
    }
    fetchProfile()
  }, [])

  const handleProfileSubmit = async (e) => {
    e.preventDefault()
    if (!firstName.trim() || !lastName.trim()) return
    setUpdatingProfile(true)
    try {
      const updated = await updateProfile(firstName, lastName)
      setProfileSuccessMsg('Profile updated! KES 50 discount applied on your next ride.')
      setProfileData(prev => ({
        ...prev,
        first_name: updated.first_name,
        last_name: updated.last_name,
        has_name: true
      }))
      // Sync local user auth state
      setUser(prev => ({
        ...prev,
        username: `${updated.first_name.toLowerCase()}_${updated.last_name.toLowerCase()}`
      }))
      setTimeout(() => {
        setShowProfileForm(false)
      }, 3000)
    } catch (err) {
      console.error("Failed to update profile:", err)
    } finally {
      setUpdatingProfile(false)
    }
  }

  const handleRecoverySubmit = async (e) => {
    e.preventDefault()
    if (!recoveryPhone.trim()) return
    setSendingRecovery(true)
    setRecoverySuccessMsg('')
    setRecoveryErrorMsg('')
    try {
      await requestDeviceMigration(recoveryPhone, deviceUuid)
      setRecoverySuccessMsg('Verification link sent via SMS! Click it to restore your tickets.')
      setRecoveryPhone('')
    } catch (err) {
      setRecoveryErrorMsg(err.response?.data?.detail || 'Failed to send recovery SMS. Please try again.')
    } finally {
      setSendingRecovery(false)
    }
  }

  const showProgressiveBanner = profileData && profileData.trip_count >= 3 && !profileData.has_name

  return (
    <div className="flex flex-col gap-6 animate-fade-in">
      
      {/* Welcome Banner */}
      <div className="bg-gradient-to-br from-[#143d2c] to-[#0a2318] text-white p-6 rounded-2xl shadow-xl relative overflow-hidden">
        {/* Subtle decorative background pattern */}
        <div className="absolute right-0 bottom-0 opacity-10 pointer-events-none transform translate-x-4 translate-y-4">
          <svg width="200" height="200" fill="currentColor" viewBox="0 0 100 100">
            <path d="M10 20 L90 20 L50 80 Z" />
          </svg>
        </div>

        <span className="text-[10px] bg-[#f1a81f] text-emerald-950 font-bold uppercase px-2.5 py-0.5 rounded-full tracking-wider">
          Frictionless Travel
        </span>
        <h1 className="text-2xl font-bold mt-3 mb-2" style={{ fontFamily: 'serif' }}>
          Welcome to Smart<span className="text-[#f1a81f]">Transit</span>
        </h1>
        <p className="text-xs text-white/80 leading-relaxed max-w-md">
          Skip the lines, track your bus in real-time, and make contactless M-Pesa payments instantly.
        </p>

        <button
          onClick={() => navigate('/commuter/plan')}
          className="mt-5 bg-[#f1a81f] text-emerald-950 font-bold text-sm px-6 py-3 rounded-xl hover:bg-yellow-500 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-md cursor-pointer inline-flex items-center gap-2"
        >
          Book a Trip Now
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        </button>
      </div>

      {/* Progressive Profile Building Banner */}
      {showProgressiveBanner && (
        <div className="bg-emerald-50 border border-emerald-200 p-5 rounded-2xl shadow-sm transition-all">
          <div className="flex items-start gap-4">
            <div className="bg-[#f1a81f] text-emerald-950 p-2.5 rounded-xl text-lg font-bold">
              🎁
            </div>
            <div className="flex-1">
              <h3 className="font-bold text-sm text-[#143d2c]">Claim your KES 50 Commuter Reward!</h3>
              <p className="text-xs text-ink-light mt-0.5 leading-relaxed">
                You have completed {profileData.trip_count} trips! Complete your profile by adding your name and get KES 50 off your next ticket.
              </p>
              
              {!showProfileForm ? (
                <button
                  onClick={() => setShowProfileForm(true)}
                  className="mt-3 text-xs font-bold text-[#143d2c] hover:text-emerald-800 transition-colors flex items-center gap-1 cursor-pointer"
                >
                  Complete profile & claim discount →
                </button>
              ) : (
                <form onSubmit={handleProfileSubmit} className="mt-4 flex flex-col gap-3 max-w-sm">
                  {profileSuccessMsg ? (
                    <p className="text-xs text-green-700 font-semibold">{profileSuccessMsg}</p>
                  ) : (
                    <>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="First Name"
                          required
                          value={firstName}
                          onChange={(e) => setFirstName(e.target.value)}
                          className="bg-white border border-gray-300 rounded-xl px-3 py-2 text-xs w-full focus:outline-none focus:border-[#143d2c]"
                        />
                        <input
                          type="text"
                          placeholder="Last Name"
                          required
                          value={lastName}
                          onChange={(e) => setLastName(e.target.value)}
                          className="bg-white border border-gray-300 rounded-xl px-3 py-2 text-xs w-full focus:outline-none focus:border-[#143d2c]"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={updatingProfile}
                        className="bg-[#143d2c] text-white text-xs font-bold py-2 rounded-xl hover:bg-emerald-950 disabled:opacity-50 transition-colors cursor-pointer"
                      >
                        {updatingProfile ? 'Saving...' : 'Submit & Claim'}
                      </button>
                    </>
                  )}
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Main Value Propositions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center text-center">
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#143d2c] flex items-center justify-center text-xl font-bold mb-3">
            📍
          </div>
          <h3 className="font-bold text-sm text-ink mb-1">Real-Time Tracking</h3>
          <p className="text-xs text-ink-light leading-relaxed">
            See exactly where your bus is and get accurate ETA updates. No more guessing.
          </p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center text-center">
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#143d2c] flex items-center justify-center text-xl font-bold mb-3">
            💺
          </div>
          <h3 className="font-bold text-sm text-ink mb-1">Guaranteed Seat</h3>
          <p className="text-xs text-ink-light leading-relaxed">
            Pre-book your ticket and secure your seat. Board stress-free.
          </p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center text-center">
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#143d2c] flex items-center justify-center text-xl font-bold mb-3">
            📱
          </div>
          <h3 className="font-bold text-sm text-ink mb-1">Frictionless M-Pesa</h3>
          <p className="text-xs text-ink-light leading-relaxed">
            Pay safely with a seamless M-Pesa STK push. Instant ticketing.
          </p>
        </div>
      </div>

      {/* Recover Ticket History / Re-entry Card */}
      <div className="bg-white p-5 rounded-2xl border border-gray-150 shadow-sm mt-2">
        <div className="flex items-start gap-4">
          <div className="text-[#f1a81f] text-2xl mt-1">🔄</div>
          <div className="flex-1">
            <h3 className="font-bold text-sm text-ink">Restore History & Session</h3>
            <p className="text-xs text-ink-light mt-0.5 leading-relaxed">
              Switched phones or lost your tickets? Enter your Safaricom number and we'll send a secure login link to recover your bookings.
            </p>
            
            <form onSubmit={handleRecoverySubmit} className="mt-4 flex flex-col sm:flex-row gap-2 max-w-md">
              <input
                type="tel"
                placeholder="e.g. 0712345678"
                required
                value={recoveryPhone}
                onChange={(e) => setRecoveryPhone(e.target.value)}
                className="bg-gray-50 border border-gray-300 rounded-xl px-4 py-2.5 text-xs w-full focus:outline-none focus:border-[#143d2c]"
              />
              <button
                type="submit"
                disabled={sendingRecovery}
                className="bg-[#143d2c] text-white text-xs font-bold px-6 py-2.5 rounded-xl hover:bg-emerald-950 transition-colors disabled:opacity-50 shrink-0 cursor-pointer"
              >
                {sendingRecovery ? 'Sending...' : 'Recover History'}
              </button>
            </form>

            {recoverySuccessMsg && (
              <p className="text-xs text-green-700 font-semibold mt-2">{recoverySuccessMsg}</p>
            )}
            {recoveryErrorMsg && (
              <p className="text-xs text-red-600 font-semibold mt-2">{recoveryErrorMsg}</p>
            )}
          </div>
        </div>
      </div>

    </div>
  )
}
