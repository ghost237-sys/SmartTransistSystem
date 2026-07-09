import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { getStages, checkIn, getMyQueueStatus, arrivedAtLoadingBay, departQueueEntry } from '../../api/stageQueue'
import { getVehicles } from '../../api/fleet'
import Button from '../../components/ui/Button'

export default function QueuePage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [selectedStage, setSelectedStage] = useState(null)
  const [selectedVehicle, setSelectedVehicle] = useState(null)

  const { data: stages, isLoading: loadingStages } = useQuery({
    queryKey: ['stages'],
    queryFn: getStages,
  })

  const { data: vehicles, isLoading: loadingVehicles } = useQuery({
    queryKey: ['vehicles'],
    queryFn: getVehicles,
  })

  // Auto-select assigned stage and vehicle when data loads
  useEffect(() => {
    if (user?.assigned_stage && stages) {
      setSelectedStage(user.assigned_stage)
    }
  }, [user, stages])

  useEffect(() => {
    if (user?.id && vehicles) {
      // Find vehicle assigned to this driver
      const assignedVehicle = vehicles.find(v => v.assigned_driver === user.id)
      if (assignedVehicle) {
        setSelectedVehicle(assignedVehicle.id)
      }
    }
  }, [user, vehicles])

  const { data: myStatus, refetch: refetchMyStatus } = useQuery({
    queryKey: ['my-queue-status'],
    queryFn: getMyQueueStatus,
    refetchInterval: 5000, // Poll every 5 seconds
  })

  const checkInMutation = useMutation({
    mutationFn: ({ stageId, vehicleId }) => checkIn(stageId, vehicleId),
    onSuccess: () => {
      queryClient.invalidateQueries(['my-queue-status'])
    },
  })

  const departMutation = useMutation({
    mutationFn: (queueEntryId) => departQueueEntry(queueEntryId),
    onSuccess: () => {
      queryClient.invalidateQueries(['my-queue-status'])
    },
  })

  const arrivedAtLoadingBayMutation = useMutation({
    mutationFn: (queueEntryId) => arrivedAtLoadingBay(queueEntryId),
    onSuccess: () => {
      queryClient.invalidateQueries(['my-queue-status'])
    },
  })

  const handleCheckIn = () => {
    if (selectedStage && selectedVehicle) {
      checkInMutation.mutate({ stageId: selectedStage, vehicleId: selectedVehicle })
    }
  }

  const handleDepart = () => {
    if (myStatus?.queue_entry?.id) {
      departMutation.mutate(myStatus.queue_entry.id)
    }
  }

  const handleArrivedAtLoadingBay = () => {
    if (myStatus?.queue_entry?.id) {
      arrivedAtLoadingBayMutation.mutate(myStatus.queue_entry.id)
    }
  }

  if (loadingStages || loadingVehicles) {
    return (
      <div className="flex justify-center py-12">
        <svg className="animate-spin h-8 w-8 text-amber" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      </div>
    )
  }

  // If driver is already in queue, show queue status
  if (myStatus?.queue_entry) {
    const entry = myStatus.queue_entry
    const isCalledUp = entry.status === 'called_up'
    
    return (
      <div className="flex flex-col gap-5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/driver')}
            className="text-white/40 hover:text-white transition-colors text-lg"
          >
            ←
          </button>
          <div>
            <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'serif' }}>
              Queue Status
            </h1>
            <p className="text-white/50 text-sm">{entry.stage_name}</p>
          </div>
        </div>

        <div className="bg-black/20 rounded-xl p-6 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-white/50 text-xs uppercase tracking-wider">Vehicle</p>
              <p className="text-white font-bold text-xl">{entry.vehicle_code || entry.vehicle_plate}</p>
            </div>
            <div className={`px-3 py-1 rounded-full text-sm font-bold ${
              entry.status === 'holding' ? 'bg-amber/20 text-amber' :
              entry.status === 'called_up' ? 'bg-green/20 text-green' :
              entry.status === 'loading' ? 'bg-blue/20 text-blue' :
              'bg-white/10 text-white/60'
            }`}>
              {entry.status.replace('_', ' ').toUpperCase()}
            </div>
          </div>

          {entry.status === 'holding' && (
            <div className="space-y-3">
              {!entry.confirmed && (
                <div className="bg-amber/10 border border-amber/30 rounded-lg p-4 text-amber text-sm">
                  ⏳ Waiting for stage manager to confirm your arrival
                </div>
              )}

              {entry.confirmed && (
                <>
                  <div className="bg-green/10 border border-green/30 rounded-lg p-4 text-green text-sm">
                    ✓ Confirmed by stage manager
                  </div>
                  <div className="bg-black/30 rounded-lg p-4">
                    <p className="text-white/50 text-xs uppercase tracking-wider mb-1">Your Position</p>
                    <p className="text-white font-bold text-4xl">{myStatus.queue_position || '—'}</p>
                    <p className="text-white/40 text-sm">{myStatus.entries_ahead} buses ahead</p>
                  </div>
                </>
              )}
            </div>
          )}

          {isCalledUp && (
            <div className="space-y-3">
              <div className="bg-green/10 border border-green/30 rounded-lg p-4 text-center">
                <p className="text-green font-bold text-lg">🚌 YOU'RE UP!</p>
                <p className="text-white/60 text-sm">Proceed to loading bay</p>
              </div>

              {entry.time_cap_exceeded && (
                <div className="bg-red-500/10 border border-red-400/30 rounded-lg p-4 text-red-200 text-sm">
                  ⚠️ Time cap exceeded - please depart promptly
                </div>
              )}
            </div>
          )}

          {entry.status === 'loading' && (
            <div className="space-y-3">
              <div className="bg-blue/10 border border-blue/30 rounded-lg p-4 text-center">
                <p className="text-blue font-bold text-lg">📍 AT LOADING BAY</p>
                <p className="text-white/60 text-sm">Loading passengers</p>
              </div>
            </div>
          )}
        </div>

        {isCalledUp && (
          <Button
            variant="success"
            className="w-full py-4 text-lg"
            onClick={handleArrivedAtLoadingBay}
            disabled={arrivedAtLoadingBayMutation.isLoading}
          >
            {arrivedAtLoadingBayMutation.isLoading ? 'CONFIRMING...' : 'ARRIVED AT LOADING BAY'}
          </Button>
        )}

        {entry.status === 'loading' && (
          <Button
            variant="success"
            className="w-full py-4 text-lg"
            onClick={handleDepart}
            disabled={departMutation.isLoading}
          >
            {departMutation.isLoading ? 'DEPARTING...' : 'DEPART STAGE'}
          </Button>
        )}

        <p className="text-white/40 text-xs text-center">
          Status updates automatically every 5 seconds
        </p>
      </div>
    )
  }

  // Show check-in form
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/driver')}
          className="text-white/40 hover:text-white transition-colors text-lg"
        >
          ←
        </button>
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'serif' }}>
            Stage Check-In
          </h1>
          <p className="text-white/50 text-sm">Join the queue at your stage</p>
        </div>
      </div>

      <div className="bg-black/20 rounded-xl p-6 border border-white/10 space-y-4">
        <div>
          <label className="block text-white/70 text-sm mb-2">Assigned Stage</label>
          <div className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-3 text-white">
            {stages?.find(s => s.id === user?.assigned_stage)?.name || 'No stage assigned'}
          </div>
        </div>

        <div>
          <label className="block text-white/70 text-sm mb-2">Assigned Vehicle</label>
          <div className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-3 text-white">
            {vehicles?.find(v => v.assigned_driver === user.id)?.fleet_code || 
             vehicles?.find(v => v.assigned_driver === user.id)?.plate_number || 
             'No vehicle assigned'}
          </div>
        </div>

        <Button
          variant="primary"
          className="w-full py-4 text-lg"
          onClick={handleCheckIn}
          disabled={(!selectedStage && !user?.assigned_stage) || (!selectedVehicle && !vehicles?.find(v => v.assigned_driver === user.id)) || checkInMutation.isLoading}
        >
          {checkInMutation.isLoading ? 'CHECKING IN...' : 'CHECK IN AT STAGE'}
        </Button>
      </div>

      {checkInMutation.error && (
        <div className="bg-red-500/10 border border-red-400/30 rounded-xl px-4 py-3 text-red-200 text-sm">
          {checkInMutation.error.response?.data?.error || 'Failed to check in'}
        </div>
      )}
    </div>
  )
}
