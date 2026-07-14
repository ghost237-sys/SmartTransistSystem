import client from './client'

export const passesApi = {
  // Get available pass tiers
  getTiers: (params = {}) => client.get('/api/passes/tiers/', { params }),
  
  // Get current user's active pass
  getMyPass: () => client.get('/api/passes/passes/my_pass/'),
  
  // Get all passes for current user
  getMyPasses: () => client.get('/api/passes/passes/'),
  
  // Create a new pass
  createPass: (data) => client.post('/api/passes/passes/', data),
  
  // Use pass for a trip
  usePass: (passId, data) => client.post(`/api/passes/passes/${passId}/use/`, data),
  
  // Renew a pass
  renewPass: (passId) => client.post(`/api/passes/passes/${passId}/renew/`),
  
  // Cancel a pass
  cancelPass: (passId) => client.post(`/api/passes/passes/${passId}/cancel/`),
  
  // Get credit score
  getCreditScore: () => client.get('/api/passes/credit-score/'),
  
  // Recalculate credit score
  recalculateCreditScore: () => client.post('/api/passes/credit-score/'),
  
  // Fleet owner functions
  getFleetTiers: () => client.get('/api/passes/fleet-tiers/'),
  
  createFleetTier: (data) => client.post('/api/passes/fleet-tiers/', data),
  
  updateFleetTier: (id, data) => client.put(`/api/passes/fleet-tiers/${id}/`, data),
  
  deleteFleetTier: (id) => client.delete(`/api/passes/fleet-tiers/${id}/`),
  
  getFleetPasses: () => client.get('/api/passes/passes/'),
}
