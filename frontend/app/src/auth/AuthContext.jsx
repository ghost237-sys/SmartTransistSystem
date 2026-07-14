import { createContext, useContext, useEffect, useState } from 'react'
import { login as apiLogin } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Rehydrate user from stored token on page load
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
        } else {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        }
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    }
    setLoading(false)
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
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)