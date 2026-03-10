import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../api/client'
import {
  AUTH_CHANGE_EVENT,
  type AuthSession,
  type LogoutReason,
  clearStoredSession,
  clearStoredLogoutReason,
  getStoredSession,
  getStoredLogoutReason,
  setStoredSession,
} from './session'

interface AuthContextValue {
  session: AuthSession | null
  login: (userId: number, password: string) => Promise<void>
  logout: (reason?: LogoutReason) => void
  secondsRemaining: number | null
  expiresSoon: boolean
  logoutReason: LogoutReason | null
  clearLogoutReason: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(() => getStoredSession())
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null)
  const [logoutReason, setLogoutReason] = useState<LogoutReason | null>(() => getStoredLogoutReason())

  useEffect(() => {
    const syncSession = () => {
      setSession(getStoredSession())
      setLogoutReason(getStoredLogoutReason())
    }
    window.addEventListener(AUTH_CHANGE_EVENT, syncSession)
    return () => window.removeEventListener(AUTH_CHANGE_EVENT, syncSession)
  }, [])

  useEffect(() => {
    if (!session) {
      setSecondsRemaining(null)
      return
    }

    const updateCountdown = () => {
      const nextSeconds = Math.max(0, Math.floor((session.expiresAt - Date.now()) / 1000))
      setSecondsRemaining(nextSeconds)
      if (nextSeconds <= 0) {
        clearStoredSession('expired')
        setSession(null)
        setLogoutReason('expired')
      }
    }

    updateCountdown()
    const intervalId = window.setInterval(updateCountdown, 1000)
    window.addEventListener('focus', updateCountdown)

    return () => {
      window.clearInterval(intervalId)
      window.removeEventListener('focus', updateCountdown)
    }
  }, [session])

  async function login(userId: number, password: string): Promise<void> {
    const token = await api.auth.login({ userId, password })
    const me = await api.auth.me(token.accessToken)
    const nextSession: AuthSession = {
      accessToken: token.accessToken,
      expiresAt: Date.now() + token.expiresInSeconds * 1000,
      user: me,
    }
    setStoredSession(nextSession)
    setSession(nextSession)
    setLogoutReason(null)
  }

  function logout(reason: LogoutReason = 'manual'): void {
    clearStoredSession(reason)
    setSession(null)
    setLogoutReason(reason)
  }

  function clearLogoutReason(): void {
    clearStoredLogoutReason()
    setLogoutReason(null)
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        login,
        logout,
        secondsRemaining,
        expiresSoon: secondsRemaining !== null && secondsRemaining <= 300,
        logoutReason,
        clearLogoutReason,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}