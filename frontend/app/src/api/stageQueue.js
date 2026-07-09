import client from './client'

export const getStages = () => client.get('/api/stage-queue/stages/').then(res => res.data)

export const checkIn = (stageId, vehicleId) =>
  client.post('/api/stage-queue/check-in/', { stage_id: stageId, vehicle_id: vehicleId }).then(res => res.data)

export const confirmQueueEntry = (queueEntryId) =>
  client.post('/api/stage-queue/confirm/', { queue_entry_id: queueEntryId }).then(res => res.data)

export const callUpQueueEntry = (queueEntryId) =>
  client.post('/api/stage-queue/call-up/', { queue_entry_id: queueEntryId }).then(res => res.data)

export const arrivedAtLoadingBay = (queueEntryId) =>
  client.post('/api/stage-queue/arrived-at-loading-bay/', { queue_entry_id: queueEntryId }).then(res => res.data)

export const departQueueEntry = (queueEntryId) =>
  client.post('/api/stage-queue/depart/', { queue_entry_id: queueEntryId }).then(res => res.data)

export const getQueueStatus = (stageId) =>
  client.get('/api/stage-queue/status/', { params: { stage_id: stageId } }).then(res => res.data)

export const getMyQueueStatus = () =>
  client.get('/api/stage-queue/my-status/').then(res => res.data)

export const getQueueEntries = (stageId) =>
  client.get('/api/stage-queue/queue-entries/', { params: { stage_id: stageId } }).then(res => res.data)

export const reorderQueueEntry = (queueEntryId, newPosition) =>
  client.post('/api/stage-queue/reorder/', { queue_entry_id: queueEntryId, new_position: newPosition }).then(res => res.data)

export const markQueueEntryFull = (queueEntryId) =>
  client.post('/api/stage-queue/mark-full/', { queue_entry_id: queueEntryId }).then(res => res.data)
