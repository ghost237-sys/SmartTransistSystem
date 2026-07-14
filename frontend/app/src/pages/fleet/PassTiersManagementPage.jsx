import { useState, useEffect } from 'react'
import { passesApi } from '../../api/passes'

export default function PassTiersManagementPage() {
  const [tiers, setTiers] = useState([])
  const [passes, setPasses] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingTier, setEditingTier] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    tier_type: 'weekly',
    trip_allowance: 10,
    discount_percent: 5,
    price: 950,
    duration_days: 7,
    min_credit_score: null,
    max_credit_limit: null,
    is_active: true
  })
  const [error, setError] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const [tiersResponse, passesResponse] = await Promise.all([
        passesApi.getFleetTiers(),
        passesApi.getFleetPasses()
      ])
      
      setTiers(tiersResponse.data.results || tiersResponse.data)
      setPasses(passesResponse.data.results || passesResponse.data)
    } catch (err) {
      console.error('Error loading data:', err)
      setError('Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateTier = async () => {
    try {
      setError(null)
      await passesApi.createFleetTier(formData)
      setShowModal(false)
      resetForm()
      await loadData()
    } catch (err) {
      console.error('Error creating tier:', err)
      setError(err.response?.data?.detail || 'Failed to create tier')
    }
  }

  const handleUpdateTier = async () => {
    if (!editingTier) return
    try {
      setError(null)
      await passesApi.updateFleetTier(editingTier.id, formData)
      setShowModal(false)
      setEditingTier(null)
      resetForm()
      await loadData()
    } catch (err) {
      console.error('Error updating tier:', err)
      setError(err.response?.data?.detail || 'Failed to update tier')
    }
  }

  const handleDeleteTier = async (tierId) => {
    if (!window.confirm('Are you sure you want to delete this tier?')) return
    try {
      setError(null)
      await passesApi.deleteFleetTier(tierId)
      await loadData()
    } catch (err) {
      console.error('Error deleting tier:', err)
      setError('Failed to delete tier')
    }
  }

  const handleEditTier = (tier) => {
    setEditingTier(tier)
    setFormData({
      name: tier.name,
      tier_type: tier.tier_type,
      trip_allowance: tier.trip_allowance,
      discount_percent: tier.discount_percent,
      price: tier.price,
      duration_days: tier.duration_days,
      min_credit_score: tier.min_credit_score,
      max_credit_limit: tier.max_credit_limit,
      is_active: tier.is_active
    })
    setShowModal(true)
  }

  const resetForm = () => {
    setFormData({
      name: '',
      tier_type: 'weekly',
      trip_allowance: 10,
      discount_percent: 5,
      price: 950,
      duration_days: 7,
      min_credit_score: null,
      max_credit_limit: null,
      is_active: true
    })
    setEditingTier(null)
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
        <h1 className="text-2xl font-bold text-gray-900">Subscription Tiers</h1>
        <button
          onClick={() => {
            resetForm()
            setShowModal(true)
          }}
          className="bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
        >
          Add New Tier
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Pass Tiers */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Active Subscription Tiers</h2>
        </div>
        <div className="divide-y">
          {tiers.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              No subscription tiers configured. Click "Add New Tier" to create one.
            </div>
          ) : (
            tiers.map((tier) => (
              <div key={tier.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold text-gray-900">{tier.name}</h3>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getTierTypeColor(tier.tier_type)}`}>
                        {getTierTypeLabel(tier.tier_type)}
                      </span>
                      {!tier.is_active && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                          Inactive
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Trips:</span>
                        <span className="ml-1 font-medium">{tier.trip_allowance}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Discount:</span>
                        <span className="ml-1 font-medium text-green-600">{tier.discount_percent}%</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Price:</span>
                        <span className="ml-1 font-medium">{tier.price > 0 ? formatCurrency(tier.price) : 'Pay as you go'}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Duration:</span>
                        <span className="ml-1 font-medium">{tier.duration_days} days</span>
                      </div>
                    </div>
                    {tier.tier_type === 'postpaid' && (
                      <div className="mt-2 text-sm">
                        <span className="text-gray-500">Credit Limit:</span>
                        <span className="ml-1 font-medium">{formatCurrency(tier.max_credit_limit)}</span>
                        {tier.min_credit_score && (
                          <>
                            <span className="text-gray-500 ml-3">Min Score:</span>
                            <span className="ml-1 font-medium">{tier.min_credit_score}</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => handleEditTier(tier)}
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDeleteTier(tier.id)}
                      className="text-sm text-red-600 hover:text-red-800 font-medium"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Active Commuter Passes */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Active Commuter Passes</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tier</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trips Used</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Balance</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expires</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {passes.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-gray-500">
                    No active commuter passes
                  </td>
                </tr>
              ) : (
                passes.map((pass) => (
                  <tr key={pass.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">
                      {pass.user?.username || 'Unknown'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {pass.tier_details?.name || 'Unknown'}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        pass.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {pass.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {pass.trips_used} / {pass.tier_details?.trip_allowance || 0}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {pass.tier_details?.tier_type === 'postpaid' 
                        ? formatCurrency(pass.current_balance)
                        : 'N/A'
                      }
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {new Date(pass.end_date).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              {editingTier ? 'Edit Subscription Tier' : 'Create Subscription Tier'}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full border rounded-lg px-3 py-2"
                  placeholder="e.g., Weekly Bundle"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tier Type</label>
                <select
                  value={formData.tier_type}
                  onChange={(e) => setFormData({...formData, tier_type: e.target.value})}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="weekly">Weekly Bundle</option>
                  <option value="monthly">Monthly Season Pass</option>
                  <option value="postpaid">Post-Paid Line</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Trip Allowance</label>
                  <input
                    type="number"
                    value={formData.trip_allowance}
                    onChange={(e) => setFormData({...formData, trip_allowance: parseInt(e.target.value)})}
                    className="w-full border rounded-lg px-3 py-2"
                    disabled={formData.tier_type === 'postpaid'}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Discount (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.discount_percent}
                    onChange={(e) => setFormData({...formData, discount_percent: parseFloat(e.target.value)})}
                    className="w-full border rounded-lg px-3 py-2"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Price (KES)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.price}
                    onChange={(e) => setFormData({...formData, price: parseFloat(e.target.value)})}
                    className="w-full border rounded-lg px-3 py-2"
                    disabled={formData.tier_type === 'postpaid'}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Duration (days)</label>
                  <input
                    type="number"
                    value={formData.duration_days}
                    onChange={(e) => setFormData({...formData, duration_days: parseInt(e.target.value)})}
                    className="w-full border rounded-lg px-3 py-2"
                  />
                </div>
              </div>

              {formData.tier_type === 'postpaid' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Credit Limit (KES)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.max_credit_limit}
                      onChange={(e) => setFormData({...formData, max_credit_limit: parseFloat(e.target.value)})}
                      className="w-full border rounded-lg px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Min Credit Score</label>
                    <input
                      type="number"
                      value={formData.min_credit_score}
                      onChange={(e) => setFormData({...formData, min_credit_score: parseInt(e.target.value)})}
                      className="w-full border rounded-lg px-3 py-2"
                    />
                  </div>
                </div>
              )}

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                  className="mr-2"
                />
                <label htmlFor="is_active" className="text-sm font-medium text-gray-700">Active</label>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowModal(false)
                  resetForm()
                }}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={editingTier ? handleUpdateTier : handleCreateTier}
                className="flex-1 bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
              >
                {editingTier ? 'Update Tier' : 'Create Tier'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
