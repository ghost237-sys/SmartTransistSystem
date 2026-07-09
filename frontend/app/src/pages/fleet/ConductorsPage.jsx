import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getStaff, createStaff, deleteStaff, updateStaff } from '../../api/staff'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { formatBusLabel } from '../../utils/busLabel'

export default function ConductorsPage() {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingConductor, setEditingConductor] = useState(null)
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirm_password: '',
    first_name: '',
    last_name: '',
    phone_number: '',
  })

  const { data: conductors, isLoading } = useQuery({
    queryKey: ['staff', 'conductor'],
    queryFn: () => getStaff('conductor'),
  })

  const createMutation = useMutation({
    mutationFn: createStaff,
    onSuccess: () => {
      queryClient.invalidateQueries(['staff'])
      setShowAddForm(false)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteStaff,
    onSuccess: () => {
      queryClient.invalidateQueries(['staff'])
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateStaff(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['staff'])
      setEditingConductor(null)
      resetForm()
    },
  })

  const resetForm = () => {
    setFormData({
      username: '',
      email: '',
      password: '',
      confirm_password: '',
      first_name: '',
      last_name: '',
      phone_number: '',
    })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (editingConductor) {
      const { password, confirm_password, ...updateData } = formData
      updateMutation.mutate({ id: editingConductor.id, data: updateData })
    } else {
      createMutation.mutate({ ...formData, role: 'conductor' })
    }
  }

  const handleEdit = (conductor) => {
    setEditingConductor(conductor)
    setFormData({
      username: conductor.username,
      email: conductor.email || '',
      password: '',
      confirm_password: '',
      first_name: conductor.first_name || '',
      last_name: conductor.last_name || '',
      phone_number: conductor.phone_number || '',
    })
    setShowAddForm(true)
  }

  const handleDelete = (id) => {
    if (confirm('Are you sure you want to delete this conductor?')) {
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
            Conductors
          </h1>
          <p className="text-ink-light mt-1">Add conductors, then assign them to vehicles on the Vehicles page</p>
        </div>
        <Button onClick={() => { setShowAddForm(!showAddForm); setEditingConductor(null); resetForm(); }}>
          {showAddForm ? 'Cancel' : '+ Add Conductor'}
        </Button>
      </div>

      {showAddForm && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-ink mb-4">
            {editingConductor ? 'Edit Conductor' : 'Add New Conductor'}
          </h2>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-ink-light mb-1">Username *</label>
                <input
                  type="text"
                  required
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                  disabled={!!editingConductor}
                />
              </div>
              <div>
                <label className="block text-sm text-ink-light mb-1">Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                />
              </div>
            </div>
            {!editingConductor && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-ink-light mb-1">Password *</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                  />
                </div>
                <div>
                  <label className="block text-sm text-ink-light mb-1">Confirm Password *</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={formData.confirm_password}
                    onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                  />
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-ink-light mb-1">First Name</label>
                <input
                  type="text"
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                />
              </div>
              <div>
                <label className="block text-sm text-ink-light mb-1">Last Name</label>
                <input
                  type="text"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm text-ink-light mb-1">Phone Number</label>
              <input
                type="text"
                value={formData.phone_number}
                onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-amber"
                placeholder="e.g. +254712345678"
              />
            </div>
            <p className="text-xs text-ink-light">
              Link this conductor to a bus under Fleet → Vehicles.
            </p>
            <div className="flex gap-3 justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => { setShowAddForm(false); setEditingConductor(null); resetForm(); }}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isLoading || updateMutation.isLoading}
              >
                {createMutation.isLoading || updateMutation.isLoading ? 'Saving...' : (editingConductor ? 'Update Conductor' : 'Add Conductor')}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <div className="flex flex-col gap-3">
        {!conductors || conductors.length === 0 ? (
          <Card className="text-center py-8">
            <p className="text-ink-light text-sm">No conductors in your fleet yet.</p>
          </Card>
        ) : (
          conductors.map(conductor => (
            <Card key={conductor.id}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-ink">{conductor.username}</p>
                  </div>
                  <p className="text-sm text-ink-light">
                    {conductor.first_name} {conductor.last_name} · {conductor.phone_number || 'No phone'}
                  </p>
                  <div className="text-xs text-ink-light mt-1">
                    {conductor.assigned_vehicle_plate
                      ? `Assigned bus: ${formatBusLabel({ vehicle_plate: conductor.assigned_vehicle_plate, fleet_code: conductor.assigned_fleet_code })}`
                      : 'Not assigned to a vehicle yet'}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleEdit(conductor)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleDelete(conductor.id)}
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
