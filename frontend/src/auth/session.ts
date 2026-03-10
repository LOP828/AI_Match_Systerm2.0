export interface SessionUser {
  userId: number
  role: string
  source: string
  privileged: boolean
}

export interface AuthSession {
  accessToken: string
  expiresAt: number
  user: SessionUser
}

export type LogoutReason = 'manual' | 'expired' | 'unauthorized' | 'invalid'

export const AUTH_STORAGE_KEY = 'ai-match-auth-session'
export const AUTH_CHANGE_EVENT = 'ai-match-auth-change'
export const AUTH_LOGOUT_REASON_KEY = 'ai-match-auth-logout-reason'

function hasWindow(): boolean {
  return typeof window !== 'undefined'
}

function dispatchAuthChange(): void {
  if (!hasWindow()) {
    return
  }
  window.dispatchEvent(new CustomEvent(AUTH_CHANGE_EVENT))
}

export function getStoredSession(): AuthSession | null {
  if (!hasWindow()) {
    return null
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw) as AuthSession
    if (!parsed?.accessToken || !parsed?.user?.userId || !parsed?.expiresAt) {
      clearStoredSession('invalid')
      return null
    }
    if (parsed.expiresAt <= Date.now()) {
      clearStoredSession('expired')
      return null
    }
    return parsed
  } catch {
    clearStoredSession('invalid')
    return null
  }
}


export function getStoredLogoutReason(): LogoutReason | null {
  if (!hasWindow()) {
    return null
  }
  const value = window.sessionStorage.getItem(AUTH_LOGOUT_REASON_KEY)
  if (value === 'manual' || value === 'expired' || value === 'unauthorized' || value === 'invalid') {
    return value
  }
  return null
}


export function clearStoredLogoutReason(): void {
  if (!hasWindow()) {
    return
  }
  window.sessionStorage.removeItem(AUTH_LOGOUT_REASON_KEY)
}

export function setStoredSession(session: AuthSession): void {
  if (!hasWindow()) {
    return
  }
  clearStoredLogoutReason()
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
  dispatchAuthChange()
}

export function clearStoredSession(reason: LogoutReason = 'manual'): void {
  if (!hasWindow()) {
    return
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY)
  window.sessionStorage.setItem(AUTH_LOGOUT_REASON_KEY, reason)
  dispatchAuthChange()
}