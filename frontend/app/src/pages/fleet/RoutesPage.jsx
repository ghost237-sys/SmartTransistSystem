import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getRoutes, createRoute, deleteRoute, updateRoute } from '../../api/routes'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'

export default function RoutesPage() {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingRoute, setEditingRoute] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    distance_km: '',
    estimated_duration_minutes: '',
    is_active: true,
  })

  const { data: routes, isLoading } = useQuery({
    queryKey: ['routes'],
    queryFn: getRoutes,
  })

  const createMutation = useMutation({
    mutationFn: createRoute,
    onSuccess: () => {
      queryClient.invalidateQueries(['routes'])
      setShowAddForm(false)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteRoute,
    onSuccess: () => {
      queryClient.invalidateQueries(['routes'])
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateRoute(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['routes'])
      setEditingRoute(null)
      resetForm()
    },
  })

  const resetForm = () => {
    setFormData({
      name: '',
      distance_km: '',
      estimated_duration_minutes: '',
      is_active: true,
    })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    // For routes, we need to provide a path (LineString). For simplicity, we'll use a default path
    // In production, this should be a map-based route builder
    const routeData = {
      ...formData,
      distance_km: parseFloat(formData.distance_km),
      estimated_duration_minutes: parseInt(formData.estimated_duration_minutes),
      path: 'LINESTRING(37.1 -1.0, 36.8 -1.3)', // Default path - should be replaced with actual route builder
    }
    
    if (editingRoute) {
      updateMutation.mutate({ id: editingRoute.id, data: routeData })
    } else {
      createMutation.mutate(routeData)
    }
  }

  const handleEdit = (route) => {
    setEditingRoute(route)
    setFormData({
      name: route.name,
      distance_km: route.distance_km,
      estimated_duration_minutes: route.estimated_duration_minutes,
      is_active: route.is_active,
    })
    setShowAddForm(true)
  }

  const handleDelete = (id) => {
    if (confirm('Are you sure you want to delete this route?')) {
      deleteMutation.mutate(id)
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <svg className="animate-spin h-8 w-8 text-amber" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-ink" style={{ fontFamily: 'serif' }}>
            Routes
          </h1>
          <p className="text-ink-light mt-1">Manage your fleet routes</p>
        </div>
        <Button onClick={() => { setShowAddForm(!showAddForm); setEditingRoute(null); resetForm(); }}>
          {showAddForm ? 'Cancel' : '+ Add Route'}
        </Button>
      </div>

      {showAddForm && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-ink mb-4">
            {editingRoute ? 'Edit Route' : 'Add New Route'}
          </h2>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-sm text-ink-light mb-1">Route Name *</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                placeholder="e.g. Thika - CBD"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-ink-light mb-1">Distance (km) *</label>
                <input
                  type="number"
                  required
                  step="0.1"
                  value={formData.distance_km}
                  onChange={(e) => setFormData({ ...formData, distance_km: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                  placeholder="e.g. 45"
                />
              </div>
              <div>
                <label className="block text-sm text-ink-light mb-1">Estimated Duration (minutes) *</label>
                <input
                  type="number"
                  required
                  value={formData.estimated_duration_minutes}
                  onChange={(e) => setFormData({ ...formData, estimated_duration_minutes: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                  placeholder="e.g. 60"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="w-4 h-4"
              />
              <label htmlFor="is_active" className="text-sm text-ink">Active</label>
            </div>
            <div className="flex gap-3 justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => { setShowAddForm(false); setEditingRoute(null); resetForm(); }}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isLoading || updateMutation.isLoading}
              >
                {createMutation.isLoading || updateMutation.isLoading ? 'Saving...' : (editingRoute ? 'Update Route' : 'Add Route')}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <div className="flex flex-col gap-3">
        {!routes || routes.length === 0 ? (
          <Card className="text-center py-8">
            <p className="text-ink-light text-sm">No routes in your fleet yet.</p>
          </Card>
        ) : (
          routes.map(route => (
            <Card key={route.id}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-ink">{route.name}</p>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      route.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {route.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <p className="text-sm text-ink-light">
                    {route.distance_km} km · {route.estimated_duration_minutes} min
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleEdit(route)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleDelete(route.id)}
                    disabled={deleteMutation.isLoading}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
