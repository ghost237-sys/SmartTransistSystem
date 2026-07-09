import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getStages, getQueueStatus, confirmQueueEntry, callUpQueueEntry, reorderQueueEntry, markQueueEntryFull } from '../../api/stageQueue'
import Button from '../../components/ui/Button'

export default function QueueDashboardPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedStage, setSelectedStage] = useState(null)
  const [editingPosition, setEditingPosition] = useState(null)

  const { data: stages, isLoading: loadingStages } = useQuery({
    queryKey: ['stages'],
    queryFn: getStages,
  })

  const { data: queueStatus, isLoading: loadingQueue } = useQuery({
    queryKey: ['queue-status', selectedStage],
    queryFn: () => getQueueStatus(selectedStage),
    enabled: !!selectedStage,
    refetchInterval: 3000, // Poll every 3 seconds for live updates
  })

  const confirmMutation = useMutation({
    mutationFn: confirmQueueEntry,
    onSuccess: () => {
      queryClient.invalidateQueries(['queue-status', selectedStage])
    },
  })

  const callUpMutation = useMutation({
    mutationFn: callUpQueueEntry,
    onSuccess: () => {
      queryClient.invalidateQueries(['queue-status', selectedStage])
    },
  })

  const reorderMutation = useMutation({
    mutationFn: ({ entryId, newPosition }) => reorderQueueEntry(entryId, newPosition),
    onSuccess: () => {
      queryClient.invalidateQueries(['queue-status', selectedStage])
      setEditingPosition(null)
    },
  })

  const markFullMutation = useMutation({
    mutationFn: markQueueEntryFull,
    onSuccess: () => {
      queryClient.invalidateQueries(['queue-status', selectedStage])
    },
  })

  const handleConfirm = (entryId) => {
    confirmMutation.mutate(entryId)
  }

  const handleCallUp = (entryId) => {
    callUpMutation.mutate(entryId)
  }

  const handleReorder = (entryId, newPosition) => {
    reorderMutation.mutate({ entryId, newPosition })
  }

  const handleMarkFull = (entryId) => {
    markFullMutation.mutate(entryId)
  }

  if (loadingStages) {
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
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/stage')}
          className="text-white/40 hover:text-white transition-colors text-lg"
        >
          ←
        </button>
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'serif' }}>
            Stage Queue Dashboard
          </h1>
          <p className="text-white/50 text-sm">Manage bus arrivals and departures</p>
        </div>
      </div>

      <div className="bg-black/20 rounded-xl p-4 border border-white/10">
        <label className="block text-white/70 text-sm mb-2">Select Stage</label>
        <select
          value={selectedStage || ''}
          onChange={(e) => setSelectedStage(e.target.value)}
          className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-amber"
        >
          <option value="">Choose a stage to manage...</option>
          {stages?.map(stage => (
            <option key={stage.id} value={stage.id}>
              {stage.name} (Capacity: {stage.loading_bay_count}/{stage.loading_bay_capacity})
            </option>
          ))}
        </select>
      </div>

      {selectedStage && loadingQueue && (
        <div className="flex justify-center py-8">
          <svg className="animate-spin h-6 w-6 text-amber" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
        </div>
      )}

      {selectedStage && queueStatus && (
        <div className="space-y-4">
          {/* Loading Bay Status */}
          <div className={`rounded-xl p-4 border ${
            queueStatus.loading_bay_available 
              ? 'bg-green/10 border-green/30' 
              : 'bg-red-500/10 border-red-400/30'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-white/50 text-xs uppercase tracking-wider">Loading Bay</p>
                <p className="text-white font-bold text-lg">
                  {queueStatus.loading_bay_count} / {queueStatus.loading_bay_capacity}
                </p>
              </div>
              <div className={`px-3 py-1 rounded-full text-sm font-bold ${
                queueStatus.loading_bay_available ? 'bg-green/20 text-green' : 'bg-red-500/20 text-red-300'
              }`}>
                {queueStatus.loading_bay_available ? 'AVAILABLE' : 'FULL'}
              </div>
            </div>
          </div>

          {/* Queue Entries */}
          {queueStatus.entries.length === 0 ? (
            <div className="bg-black/20 rounded-xl p-8 text-center border border-white/10">
              <p className="text-white/50">No buses in queue</p>
            </div>
          ) : (
            <div className="space-y-3">
              {queueStatus.entries.map((entry, index) => (
                <div
                  key={entry.id}
                  className={`bg-black/20 rounded-xl p-4 border ${
                    entry.status === 'called_up' || entry.status === 'loading'
                      ? 'border-green/30 bg-green/5'
                      : entry.status === 'holding' && !entry.confirmed
                      ? 'border-amber/30 bg-amber/5'
                      : 'border-white/10'
                  }`}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <p className="text-white font-bold text-lg">
                          {entry.vehicle_code || entry.vehicle_plate}
                        </p>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                          entry.status === 'holding' && !entry.confirmed ? 'bg-amber/20 text-amber' :
                          entry.status === 'holding' && entry.confirmed ? 'bg-blue/20 text-blue' :
                          entry.status === 'called_up' ? 'bg-green/20 text-green' :
                          entry.status === 'loading' ? 'bg-purple/20 text-purple' :
                          'bg-white/10 text-white/60'
                        }`}>
                          {entry.status.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-white/50 text-sm mt-1">
                        Driver: {entry.driver_name} · Position: {entry.queue_position || '—'}
                      </p>
                      {entry.conductor_name && (
                        <p className="text-white/50 text-sm">
                          Conductor: {entry.conductor_name}
                        </p>
                      )}
                      {entry.time_cap_exceeded && (
                        <p className="text-red-300 text-xs mt-1">⚠️ Time cap exceeded</p>
                      )}
                    </div>

                    <div className="flex gap-2">
                      {entry.status === 'holding' && !entry.confirmed && (
                        <Button
                          variant="success"
                          size="sm"
                          onClick={() => handleConfirm(entry.id)}
                          disabled={confirmMutation.isLoading}
                        >
                          Confirm
                        </Button>
                      )}
                      {entry.status === 'holding' && entry.confirmed && (
                        <>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleCallUp(entry.id)}
                            disabled={callUpMutation.isLoading || !queueStatus.loading_bay_available}
                          >
                            Call Up
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => setEditingPosition(editingPosition === entry.id ? null : entry.id)}
                          >
                            {editingPosition === entry.id ? 'Cancel' : 'Move'}
                          </Button>
                        </>
                      )}
                      {entry.status === 'loading' && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleMarkFull(entry.id)}
                          disabled={markFullMutation.isLoading}
                        >
                          Mark Full
                        </Button>
                      )}
                    </div>
                  </div>
                  {editingPosition === entry.id && (
                    <div className="mt-3 pt-3 border-t border-white/10">
                      <label className="block text-white/70 text-xs mb-2">Move to position:</label>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min="1"
                          max={queueStatus.entries.length}
                          defaultValue={entry.queue_position || 1}
                          className="w-20 bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-amber"
                          id={`position-${entry.id}`}
                        />
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            const newPosition = parseInt(document.getElementById(`position-${entry.id}`).value)
                            handleReorder(entry.id, newPosition)
                          }}
                          disabled={reorderMutation.isLoading}
                        >
                          Save
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <p className="text-white/40 text-xs text-center">
        Queue updates automatically every 3 seconds
      </p>
    </div>
  )
}
