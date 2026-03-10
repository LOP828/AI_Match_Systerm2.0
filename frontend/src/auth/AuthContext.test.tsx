import { act, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { AUTH_STORAGE_KEY, type AuthSession } from './session'

function Probe() {
  const { session, logoutReason } = useAuth()
  return (
    <div>
      <span>{session ? `session:${session.user.userId}` : 'session:none'}</span>
      <span>{logoutReason ? `reason:${logoutReason}` : 'reason:none'}</span>
    </div>
  )
}

describe('AuthProvider session expiry', () => {
  it('clears the session after the expiry timer elapses', async () => {
    vi.useFakeTimers()

    const session: AuthSession = {
      accessToken: 'token',
      expiresAt: Date.now() + 1000,
      user: {
        userId: 101,
        role: 'user',
        source: 'jwt',
        privileged: false,
      },
    }
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    expect(screen.getByText('session:101')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })

    expect(screen.getByText('session:none')).toBeInTheDocument()
    expect(screen.getByText('reason:expired')).toBeInTheDocument()

    vi.useRealTimers()
  })
})