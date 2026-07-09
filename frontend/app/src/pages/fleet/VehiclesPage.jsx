import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getVehicles, createVehicle, updateVehicle } from '../../api/fleet'
import { getStaff } from '../../api/staff'
import { getRoutes } from '../../api/routes'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'

export default function VehiclesPage() {
  const queryClient = useQueryClient()
  const formRef = useRef(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingVehicle, setEditingVehicle] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [formData, setFormData] = useState({
    plate_number: '',
    fleet_code: '',
    vehicle_type: 'matatu',
    capacity: 14,
    assigned_route: '',
    assigned_driver: '',
    assigned_conductor: '',
  })

  // Scroll to form when it's shown
  useEffect(() => {
    if (showAddForm && formRef.current) {
      formRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [showAddForm])

  const { data: vehicles, isLoading } = useQuery({
    queryKey: ['vehicles'],
    queryFn: getVehicles,
  })

  const { data: drivers } = useQuery({
    queryKey: ['staff', 'driver'],
    queryFn: () => getStaff('driver'),
  })

  const { data: conductors } = useQuery({
    queryKey: ['staff', 'conductor'],
    queryFn: () => getStaff('conductor'),
  })

  const { data: routes } = useQuery({
    queryKey: ['routes'],
    queryFn: getRoutes,
  })

  // Filter vehicles based on search query
  const filteredVehicles = vehicles?.filter(vehicle => {
    const query = searchQuery.toLowerCase()
    return (
      vehicle.plate_number?.toLowerCase().includes(query) ||
      vehicle.fleet_code?.toLowerCase().includes(query) ||
      vehicle.assigned_driver_username?.toLowerCase().includes(query) ||
      vehicle.assigned_conductor_username?.toLowerCase().includes(query) ||
      vehicle.assigned_route_name?.toLowerCase().includes(query)
    )
  }) || []

  const createMutation = useMutation({
    mutationFn: createVehicle,
    onSuccess: () => {
      queryClient.invalidateQueries(['vehicles'])
      setShowAddForm(false)
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateVehicle(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['vehicles'])
      setEditingVehicle(null)
      resetForm()
    },
  })

  const resetForm = () => {
    setFormData({
      plate_number: '',
      fleet_code: '',
      vehicle_type: 'matatu',
      capacity: 14,
      assigned_route: '',
      assigned_driver: '',
      assigned_conductor: '',
    })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (editingVehicle) {
      updateMutation.mutate({ id: editingVehicle.id, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handleEdit = (vehicle) => {
    setEditingVehicle(vehicle)
    setFormData({
      plate_number: vehicle.plate_number,
      fleet_code: vehicle.fleet_code || '',
      vehicle_type: vehicle.vehicle_type,
      capacity: vehicle.capacity,
      assigned_route: vehicle.assigned_route || '',
      assigned_driver: vehicle.assigned_driver || '',
      assigned_conductor: vehicle.assigned_conductor || '',
    })
    setShowAddForm(true)
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
            Vehicles
          </h1>
          <p className="text-ink-light mt-1">Manage your fleet vehicles</p>
        </div>
        <Button onClick={() => { setShowAddForm(!showAddForm); setEditingVehicle(null); resetForm(); }}>
          {showAddForm ? 'Cancel' : '+ Add Vehicle'}
        </Button>
      </div>

      <div className="relative">
        <input
          type="text"
          placeholder="Search vehicles by plate, code, driver, conductor, or route..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-4 py-2 pl-10 focus:outline-none focus:border-amber"
        />
        <svg className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </div>

      {showAddForm && (
        <Card className="p-6" ref={formRef}>
          <h2 className="text-lg font-semibold text-ink mb-4">
            {editingVehicle ? 'Edit Vehicle' : 'Add New Vehicle'}
          </h2>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-ink-light mb-1">Plate Number *</label>
                <input
                  type="text"
                  required
                  value={formData.plate_number}
                  onChange={(e) => setFormData({ ...formData, plate_number: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                  placeholder="e.g. KDA 123A"
                  disabled={!!editingVehicle}
                />
              </div>
              <div>
                <label className="block text-sm text-ink-light mb-1">Fleet Code</label>
                <input
                  type="text"
                  value={formData.fleet_code}
                  onChange={(e) => setFormData({ ...formData, fleet_code: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                  placeholder="e.g. TH-001"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-ink-light mb-1">Vehicle Type</label>
                <select
                  value={formData.vehicle_type}
                  onChange={(e) => setFormData({ ...formData, vehicle_type: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                >
                  <option value="matatu">Matatu</option>
                  <option value="bus">Bus</option>
                  <option value="shuttle">Shuttle</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-ink-light mb-1">Capacity (passengers)</label>
                <input
                  type="number"
                  required
                  min="1"
                  value={formData.capacity}
                  onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm text-ink-light mb-1">Assigned Route</label>
              <select
                value={formData.assigned_route}
                onChange={(e) => setFormData({ ...formData, assigned_route: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
              >
                <option value="">No route assigned</option>
                {routes?.map(route => (
                  <option key={route.id} value={route.id}>{route.name}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-ink-light mb-1">Assigned Driver</label>
                <select
                  value={formData.assigned_driver}
                  onChange={(e) => setFormData({ ...formData, assigned_driver: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                >
                  <option value="">No driver assigned</option>
                  {drivers?.map(driver => (
                    <option key={driver.id} value={driver.id}>{driver.username}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-ink-light mb-1">Assigned Conductor</label>
                <select
                  value={formData.assigned_conductor}
                  onChange={(e) => setFormData({ ...formData, assigned_conductor: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                >
                  <option value="">No conductor assigned</option>
                  {conductors?.map(conductor => (
                    <option key={conductor.id} value={conductor.id}>{conductor.username}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-3 justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => { setShowAddForm(false); setEditingVehicle(null); resetForm(); }}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isLoading || updateMutation.isLoading}
              >
                {createMutation.isLoading || updateMutation.isLoading ? 'Saving...' : (editingVehicle ? 'Update Vehicle' : 'Add Vehicle')}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <div className="flex flex-col gap-3">
        {!vehicles || vehicles.length === 0 ? (
          <Card className="text-center py-8">
            <p className="text-ink-light text-sm">No vehicles in your fleet yet.</p>
          </Card>
        ) : (
          vehicles.map(vehicle => (
            <Card key={vehicle.id}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-ink">
                      {vehicle.fleet_code || vehicle.plate_number}
                    </p>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      vehicle.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {vehicle.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <p className="text-sm text-ink-light">
                    {vehicle.plate_number} · {vehicle.vehicle_type} · {vehicle.capacity} seats
                  </p>
                  <div className="text-xs text-ink-light mt-1">
                    {vehicle.assigned_driver_username && `Driver: ${vehicle.assigned_driver_username}`}
                    {vehicle.assigned_driver_username && vehicle.assigned_conductor_username && ' · '}
                    {vehicle.assigned_conductor_username && `Conductor: ${vehicle.assigned_conductor_username}`}
                    {!vehicle.assigned_driver_username && !vehicle.assigned_conductor_username && 'No staff assigned'}
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleEdit(vehicle)}
                >
                  Edit
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
