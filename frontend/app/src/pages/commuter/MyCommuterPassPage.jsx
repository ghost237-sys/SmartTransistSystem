import { useState, useEffect } from 'react'
import { passesApi } from '../../api/passes'

export default function MyCommuterPassPage() {
  const [activePass, setActivePass] = useState(null)
  const [availableTiers, setAvailableTiers] = useState([])
  const [creditScore, setCreditScore] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showPurchaseModal, setShowPurchaseModal] = useState(false)
  const [selectedTier, setSelectedTier] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Load active pass
      const myPassResponse = await passesApi.getMyPass()
      if (myPassResponse.data) {
        setActivePass(myPassResponse.data)
      }
      
      // Load available tiers
      const tiersResponse = await passesApi.getTiers()
      setAvailableTiers(tiersResponse.data.results || tiersResponse.data)
      
      // Load credit score
      try {
        const creditResponse = await passesApi.getCreditScore()
        setCreditScore(creditResponse.data)
      } catch (e) {
        // Credit score might not exist yet
        console.log('No credit score yet')
      }
    } catch (err) {
      console.error('Error loading pass data:', err)
      setError('Failed to load pass data')
    } finally {
      setLoading(false)
    }
  }

  const handlePurchasePass = async (tier) => {
    try {
      setError(null)
      await passesApi.createPass({ tier: tier.id, auto_renew: false })
      setShowPurchaseModal(false)
      setSelectedTier(null)
      await loadData()
    } catch (err) {
      console.error('Error purchasing pass:', err)
      setError(err.response?.data?.detail || 'Failed to purchase pass')
    }
  }

  const handleRenewPass = async () => {
    if (!activePass) return
    try {
      setError(null)
      await passesApi.renewPass(activePass.id)
      await loadData()
    } catch (err) {
      console.error('Error renewing pass:', err)
      setError('Failed to renew pass')
    }
  }

  const handleCancelPass = async () => {
    if (!activePass) return
    if (!window.confirm('Are you sure you want to cancel this pass?')) return
    
    try {
      setError(null)
      await passesApi.cancelPass(activePass.id)
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

  const formatCurrency = (amount) => {
    return `KES ${parseFloat(amount).toLocaleString('en-KE')}`
  }

  const getTierTypeLabel = (type) => {
    const labels = {
      weekly: 'Weekly Bundle',
      monthly: 'Monthly Season Pass',
      postpaid: 'Post-Paid Line'
    }
    return labels[type] || type
  }

  const getTierTypeColor = (type) => {
    const colors = {
      weekly: 'bg-blue-100 text-blue-800',
      monthly: 'bg-purple-100 text-purple-800',
      postpaid: 'bg-green-100 text-green-800'
    }
    return colors[type] || 'bg-gray-100 text-gray-800'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">My Commuter Pass</h1>
        {creditScore && (
          <div className="bg-white rounded-lg px-4 py-2 shadow-sm">
            <span className="text-sm text-gray-600">Credit Score:</span>
            <span className="ml-2 font-bold text-green-600">{creditScore.score}/100</span>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Active Pass Section */}
      {activePass ? (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="bg-gradient-to-r from-green-600 to-green-700 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white">{activePass.tier_details.name}</h2>
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium mt-2 ${getTierTypeColor(activePass.tier_details.tier_type)}`}>
                  {getTierTypeLabel(activePass.tier_details.tier_type)}
                </span>
              </div>
              <div className="text-right">
                <div className="text-3xl font-bold text-white">
                  {activePass.tier_details.tier_type === 'postpaid' 
                    ? formatCurrency(activePass.current_balance)
                    : `${activePass.trips_remaining} trips`
                  }
                </div>
                <div className="text-green-100 text-sm">
                  {activePass.tier_details.tier_type === 'postpaid' ? 'Current Balance' : 'Remaining'}
                </div>
              </div>
            </div>
          </div>
          
          <div className="px-6 py-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm text-gray-500">Valid Until</div>
                <div className="font-semibold text-gray-900">{formatDate(activePass.end_date)}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Discount</div>
                <div className="font-semibold text-green-600">{activePass.tier_details.discount_percent}% off</div>
              </div>
              {activePass.tier_details.tier_type === 'postpaid' && (
                <>
                  <div>
                    <div className="text-sm text-gray-500">Credit Limit</div>
                    <div className="font-semibold text-gray-900">{formatCurrency(activePass.credit_limit)}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500">Status</div>
                    <div className="font-semibold text-green-600 capitalize">{activePass.status}</div>
                  </div>
                </>
              )}
            </div>

            {activePass.tier_details.tier_type !== 'postpaid' && (
              <div className="pt-4 border-t">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Trips Used</span>
                  <span className="font-semibold text-gray-900">{activePass.trips_used} / {activePass.tier_details.trip_allowance}</span>
                </div>
                <div className="mt-2 bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-green-600 h-2 rounded-full transition-all"
                    style={{ width: `${(activePass.trips_used / activePass.tier_details.trip_allowance) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Recent Transactions */}
            {activePass.recent_transactions && activePass.recent_transactions.length > 0 && (
              <div className="pt-4 border-t">
                <h3 className="text-sm font-semibold text-gray-700 mb-2">Recent Transactions</h3>
                <div className="space-y-2">
                  {activePass.recent_transactions.slice(0, 3).map((tx) => (
                    <div key={tx.id} className="flex items-center justify-between text-sm py-2 border-b last:border-0">
                      <div>
                        <div className="font-medium text-gray-900 capitalize">{tx.transaction_type}</div>
                        <div className="text-gray-500 text-xs">{new Date(tx.created_at).toLocaleDateString()}</div>
                      </div>
                      <div className={`font-semibold ${tx.transaction_type === 'charge' ? 'text-red-600' : 'text-green-600'}`}>
                        {tx.transaction_type === 'charge' ? '-' : '+'}{formatCurrency(tx.amount)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="pt-4 border-t flex gap-3">
              {activePass.tier_details.tier_type !== 'postpaid' && (
                <button
                  onClick={handleRenewPass}
                  className="flex-1 bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
                >
                  Renew Pass
                </button>
              )}
              <button
                onClick={handleCancelPass}
                className="px-4 py-2 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* No Active Pass */
        <div className="bg-white rounded-xl shadow-sm p-8 text-center">
          <div className="text-gray-400 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Active Pass</h3>
          <p className="text-gray-600 mb-6">Purchase a commuter pass to save on your daily trips</p>
          <button
            onClick={() => setShowPurchaseModal(true)}
            className="bg-green-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
          >
            View Available Passes
          </button>
        </div>
      )}

      {/* Available Passes Section */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Passes</h2>
        <div className="grid gap-4">
          {availableTiers.map((tier) => (
            <div key={tier.id} className="border rounded-lg p-4 hover:border-green-300 transition-colors">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-gray-900">{tier.name}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getTierTypeColor(tier.tier_type)}`}>
                      {getTierTypeLabel(tier.tier_type)}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    {tier.tier_type === 'postpaid' 
                      ? `Pay later with ${tier.discount_percent}% discount on every trip`
                      : `${tier.trip_allowance} trips with ${tier.discount_percent}% discount`
                    }
                  </p>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-500">
                      {tier.tier_type === 'postpaid' 
                        ? `Credit limit: ${formatCurrency(tier.max_credit_limit)}`
                        : `Valid for ${tier.duration_days} days`
                      }
                    </span>
                    {tier.min_credit_score && (
                      <span className="text-gray-500">Min credit score: {tier.min_credit_score}</span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold text-green-600">
                    {tier.price > 0 ? formatCurrency(tier.price) : 'Pay as you go'}
                  </div>
                  {activePass?.tier?.id !== tier.id && (
                    <button
                      onClick={() => {
                        setSelectedTier(tier)
                        setShowPurchaseModal(true)
                      }}
                      className="mt-2 text-sm bg-green-600 text-white px-4 py-1.5 rounded-lg hover:bg-green-700 transition-colors"
                    >
                      Purchase
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Purchase Modal */}
      {showPurchaseModal && selectedTier && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-4">Purchase Pass</h3>
            <div className="bg-gray-50 rounded-lg p-4 mb-4">
              <h4 className="font-semibold text-gray-900">{selectedTier.name}</h4>
              <p className="text-sm text-gray-600 mt-1">{getTierTypeLabel(selectedTier.tier_type)}</p>
              <div className="mt-3 text-2xl font-bold text-green-600">
                {selectedTier.price > 0 ? formatCurrency(selectedTier.price) : 'Pay as you go'}
              </div>
            </div>
            <div className="space-y-2 text-sm text-gray-600 mb-6">
              <p>• {selectedTier.trip_allowance} trips included</p>
              <p>• {selectedTier.discount_percent}% discount on every trip</p>
              <p>• Valid for {selectedTier.duration_days} days</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowPurchaseModal(false)
                  setSelectedTier(null)
                }}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handlePurchasePass(selectedTier)}
                className="flex-1 bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
              >
                Confirm Purchase
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
