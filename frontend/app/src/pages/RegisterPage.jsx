import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'

export default function RegisterPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    username: '',
    firstName: '',
    lastName: '',
    phoneNumber: '',
    password: '',
    confirmPassword: '',
  })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      await client.post('/api/accounts/register/', {
        username: form.username,
        first_name: form.firstName,
        last_name: form.lastName,
        phone_number: form.phoneNumber,
        password: form.password,
      })
      
      setSuccess('Account created successfully! Redirecting to login...')
      setTimeout(() => {
        navigate('/login')
      }, 2000)
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.response?.data?.username?.[0] ||
        'Registration failed. Please verify your details and try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <a href="/" className="inline-block">
            <h1 className="text-3xl font-bold" style={{ fontFamily: 'serif' }}>
              <span className="text-green-deep">Smart</span>
              <span className="text-amber">Transit</span>
            </h1>
          </a>
          <p className="text-ink-light mt-2 text-sm">Create an account to start booking rides</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="First Name"
                type="text"
                placeholder="First name"
                value={form.firstName}
                onChange={(e) => setForm(f => ({ ...f, firstName: e.target.value }))}
                required
              />
              <Input
                label="Last Name"
                type="text"
                placeholder="Last name"
                value={form.lastName}
                onChange={(e) => setForm(f => ({ ...f, lastName: e.target.value }))}
                required
              />
            </div>

            <Input
              label="Username"
              type="text"
              placeholder="Choose a username"
              value={form.username}
              onChange={(e) => setForm(f => ({ ...f, username: e.target.value }))}
              required
            />

            <Input
              label="Phone Number"
              type="tel"
              placeholder="e.g. 0712345678"
              value={form.phoneNumber}
              onChange={(e) => setForm(f => ({ ...f, phoneNumber: e.target.value }))}
              required
            />

            <Input
              label="Password"
              type="password"
              placeholder="Create password"
              value={form.password}
              onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))}
              required
            />

            <Input
              label="Confirm Password"
              type="password"
              placeholder="Confirm password"
              value={form.confirmPassword}
              onChange={(e) => setForm(f => ({ ...f, confirmPassword: e.target.value }))}
              required
            />

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
                {error}
              </div>
            )}

            {success && (
              <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-xl px-4 py-3">
                {success}
              </div>
            )}

            <Button type="submit" loading={loading} className="w-full mt-2">
              Sign Up
            </Button>
          </form>

          <div className="text-center mt-6 text-sm text-ink-light">
            Already have an account?{' '}
            <button
              onClick={() => navigate('/login')}
              className="text-green-deep hover:underline font-semibold focus:outline-none"
            >
              Sign In
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-ink-light mt-6">
          SmartTransit — Know your bus is coming.{' '}
          <a href="/" className="text-green-deep hover:underline">Back to home</a>
        </p>
      </div>
    </div>
  )
}