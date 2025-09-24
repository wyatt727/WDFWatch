'use client'

import { signIn } from 'next-auth/react'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Lock } from 'lucide-react'

export default function LoginPage() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    
    const result = await signIn('credentials', {
      username: 'admin',
      password,
      redirect: false,
    })

    setIsLoading(false)

    if (result?.error) {
      setError('Invalid password')
      // Clear password on error
      setPassword('')
    } else {
      router.push('/')
      router.refresh()
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-950 to-gray-900">
      <div className="max-w-md w-full space-y-8 p-8">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 flex items-center justify-center rounded-full bg-blue-600 mb-4">
            <Lock className="h-6 w-6 text-white" />
          </div>
          <h2 className="text-3xl font-bold text-white">
            WDFWatch
          </h2>
          <p className="mt-2 text-sm text-gray-400">
            Enter your admin password to continue
          </p>
        </div>
        
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="password" className="sr-only">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              disabled={isLoading}
              className="appearance-none rounded-md relative block w-full px-4 py-3 border border-gray-700 bg-gray-900 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              placeholder="Admin Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
            />
          </div>
          
          {error && (
            <div className="rounded-md bg-red-900/20 p-3 border border-red-900/50">
              <p className="text-red-400 text-sm text-center">{error}</p>
            </div>
          )}
          
          <div>
            <button
              type="submit"
              disabled={isLoading || !password}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>
        </form>
        
        <div className="text-center">
          <p className="text-xs text-gray-500">
            Secured WDFWatch deployment
          </p>
        </div>
      </div>
    </div>
  )
}