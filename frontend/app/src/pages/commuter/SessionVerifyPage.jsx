import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { verifyDeviceMigration } from '../../api/auth'

export default function SessionVerifyPage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { setUser } = useAuth()
  
  const [verifying, setVerifying] = useState(true)
  const [errorMsg, setErrorMsg] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  useEffect(() => {
    const runVerification = async () => {
      try {
        const data = await verifyDeviceMigration(token)
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
        
        setSuccessMsg('Session verified successfully! Restoring history...')
        setTimeout(() => {
          navigate('/commuter')
        }, 2000)
      } catch (err) {
        setErrorMsg(err.response?.data?.detail || 'Verification failed. The link may have expired or is invalid.')
      } finally {
        setVerifying(false)
      }
    }
    runVerification()
  }, [token, navigate, setUser])

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <div className="bg-white p-8 rounded-2xl border border-gray-150 shadow-xl max-w-sm w-full">
        {verifying ? (
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-4 border-[#143d2c] border-t-transparent rounded-full animate-spin" />
            <h3 className="font-bold text-ink">Verifying Session Link...</h3>
            <p className="text-xs text-ink-light leading-relaxed">
              We are connecting you securely back into your commuter session.
            </p>
          </div>
        ) : errorMsg ? (
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 bg-red-50 text-red-600 rounded-full flex items-center justify-center text-xl font-bold">
              ⚠️
            </div>
            <h3 className="font-bold text-ink">Verification Failed</h3>
            <p className="text-xs text-red-600 leading-relaxed font-semibold">
              {errorMsg}
            </p>
            <button
              onClick={() => navigate('/commuter')}
              className="mt-2 w-full bg-[#143d2c] text-white text-xs font-bold py-3 rounded-xl hover:bg-emerald-950 transition-colors cursor-pointer"
            >
              Go to Dashboard Home
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 bg-green-50 text-[#143d2c] rounded-full flex items-center justify-center text-xl font-bold">
              ✓
            </div>
            <h3 className="font-bold text-ink">Link Verified!</h3>
            <p className="text-xs text-green-700 leading-relaxed font-semibold">
              {successMsg}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
