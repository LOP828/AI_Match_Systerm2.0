/* eslint-disable react-refresh/only-export-components */

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
  const [now, setNow] = useState(() => Date.now())
  const [logoutReason, setLogoutReason] = useState<LogoutReason | null>(() => getStoredLogoutReason())

  const secondsRemaining = session ? Math.max(0, Math.floor((session.expiresAt - now) / 1000)) : null
  const expiresSoon = secondsRemaining !== null && secondsRemaining <= 300

  useEffect(() => {
    const syncSession = () => {
      setSession(getStoredSession())
      setLogoutReason(getStoredLogoutReason())
      setNow(Date.now())
    }
    window.addEventListener(AUTH_CHANGE_EVENT, syncSession)
    return () => window.removeEventListener(AUTH_CHANGE_EVENT, syncSession)
  }, [])

  useEffect(() => {
    if (!session) {
      return
    }

    const updateNow = () => setNow(Date.now())
    const intervalId = window.setInterval(updateNow, 1000)
    window.addEventListener('focus', updateNow)

    return () => {
      window.clearInterval(intervalId)
      window.removeEventListener('focus', updateNow)
    }
  }, [session])

  useEffect(() => {
    if (session && secondsRemaining === 0) {
      clearStoredSession('expired')
    }
  }, [secondsRemaining, session])

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
    setNow(Date.now())
    setLogoutReason(null)
  }

  function logout(reason: LogoutReason = 'manual'): void {
    clearStoredSession(reason)
    setSession(null)
    setNow(Date.now())
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
        expiresSoon,
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