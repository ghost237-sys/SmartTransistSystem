import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { register } from '../api/auth'
import { useAuth } from '../auth/AuthContext'
import { login as apiLogin } from '../api/auth'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [form, setForm] = useState({
    username: '',
    first_name: '',
    last_name: '',
    email: '',
    phone_number: '',
    password: '',
    confirm_password: '',
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  const update = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setLoading(true)
    try {
      await register(form)
      // Auto-login after registration
      await login(form.username, form.password)
      navigate('/commuter', { replace: true })
    } catch (err) {
      const data = err.response?.data
      if (data && typeof data === 'object') {
        setErrors(data)
      } else {
        setErrors({ detail: 'Registration failed. Please try again.' })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold" style={{ fontFamily: 'serif' }}>
            <span className="text-green-deep">Smart</span>
            <span className="text-amber">Transit</span>
          </h1>
          <p className="text-ink-light mt-2 text-sm">Create your commuter account</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">

            <div className="grid grid-cols-2 gap-3">
              <Input
                label="First name"
                type="text"
                placeholder="John"
                value={form.first_name}
                onChange={update('first_name')}
                error={errors.first_name}
              />
              <Input
                label="Last name"
                type="text"
                placeholder="Kamau"
                value={form.last_name}
                onChange={update('last_name')}
                error={errors.last_name}
              />
            </div>

            <Input
              label="Username"
              type="text"
              placeholder="johnkamau"
              value={form.username}
              onChange={update('username')}
              error={errors.username}
              required
            />

            <Input
              label="Phone number"
              type="tel"
              placeholder="0712 345 678"
              value={form.phone_number}
              onChange={update('phone_number')}
              error={errors.phone_number}
            />

            <Input
              label="Email (optional)"
              type="email"
              placeholder="john@example.com"
              value={form.email}
              onChange={update('email')}
              error={errors.email}
            />

            <Input
              label="Password"
              type="password"
              placeholder="At least 8 characters"
              value={form.password}
              onChange={update('password')}
              error={errors.password}
              required
            />

            <Input
              label="Confirm password"
              type="password"
              placeholder="Repeat your password"
              value={form.confirm_password}
              onChange={update('confirm_password')}
              error={errors.confirm_password}
              required
            />

            {errors.detail && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
                {errors.detail}
              </div>
            )}

            <Button type="submit" loading={loading} className="w-full mt-2">
              Create account
            </Button>
          </form>

          <p className="text-center text-sm text-ink-light mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-green-mid font-medium hover:text-green-deep transition-colors">
              Sign in
            </Link>
          </p>
        </div>

        <p className="text-center text-xs text-ink-light mt-6">
          SmartTransit — Know your bus is coming.
        </p>
      </div>
    </div>
  )
}