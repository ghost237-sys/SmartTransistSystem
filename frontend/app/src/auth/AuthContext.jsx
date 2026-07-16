import { createContext, useContext, useEffect, useState } from 'react'
import { login as apiLogin } from '../api/auth'

const AuthContext = createContext(null)

const generateUUID = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

import { deviceHandshake } from '../api/auth'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [deviceUuid, setDeviceUuid] = useState(null)

  useEffect(() => {
    // 1. Ensure device_uuid exists in localStorage
    let storedUuid = localStorage.getItem('device_uuid')
    if (!storedUuid) {
      storedUuid = generateUUID()
      localStorage.setItem('device_uuid', storedUuid)
    }
    setDeviceUuid(storedUuid)

    // 2. Rehydrate user or perform handshake
    const token = localStorage.getItem('access_token')
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        if (payload.exp * 1000 > Date.now()) {
          setUser({
            id: payload.user_id,
            role: payload.role,
            tenantId: payload.tenant_id,
            username: payload.username,
            phoneNumber: payload.phone_number ?? null,
            demoLat: payload.demo_lat ?? null,
            demoLng: payload.demo_lng ?? null,
            demoLocationLabel: payload.demo_location_label ?? null,
          })
          setLoading(false)
          return
        } else {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        }
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    }

    // Handshake for guest commuter session
    const performHandshake = async () => {
      try {
        const data = await deviceHandshake(storedUuid)
        localStorage.setItem('access_token', data.access)
        localStorage.setItem('refresh_token', data.refresh)
        const payload = JSON.parse(atob(data.access.split('.')[1]))
        setUser({
          id: payload.user_id,
          role: payload.role,
          tenantId: payload.tenant_id,
          username: payload.username,
          phoneNumber: payload.phone_number ?? null,
          demoLat: payload.demo_lat ?? null,
          demoLng: payload.demo_lng ?? null,
          demoLocationLabel: payload.demo_location_label ?? null,
        })
      } catch (err) {
        console.error("Device handshake failed:", err)
      } finally {
        setLoading(false)
      }
    }

    performHandshake()
  }, [])

  const login = async (username, password) => {
    try {
      // No curly braces around 'data' here, because apiLogin already returns res.data!
      const data = await apiLogin(username, password)

      if (!data || !data.access) {
        throw new Error("No access token received from backend")
      }

      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)
      
      const payload = JSON.parse(atob(data.access.split('.')[1]))
      const user = {
        id: payload.user_id,
        role: payload.role,
        tenantId: payload.tenant_id,
        username: payload.username,
        phoneNumber: payload.phone_number ?? null,
        demoLat: payload.demo_lat ?? null,
        demoLng: payload.demo_lng ?? null,
        demoLocationLabel: payload.demo_location_label ?? null,
      }
      
      setUser(user)
      return user
    } catch (error) {
      console.error("Login execution failed on frontend:", error)
      throw error 
    }
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, setUser, login, logout, loading, deviceUuid }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)