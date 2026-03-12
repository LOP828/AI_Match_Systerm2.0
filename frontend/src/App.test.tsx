import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { AUTH_STORAGE_KEY, type AuthSession } from './auth/session'

vi.mock('./pages/Dashboard', () => ({
  default: () => <div>Dashboard Mock</div>,
}))

vi.mock('./pages/UserProfile', () => ({
  default: () => <div>UserProfile Mock</div>,
}))

vi.mock('./pages/RecommendationResults', () => ({
  default: () => <div>RecommendationResults Mock</div>,
}))

vi.mock('./pages/VerifyTasks', () => ({
  default: () => <div>VerifyTasks Mock</div>,
}))

vi.mock('./pages/FeedbackForm', () => ({
  default: () => <div>FeedbackForm Mock</div>,
}))

vi.mock('./pages/AIExtractionReview', () => ({
  default: () => <div>AIExtractionReview Mock</div>,
}))

function storeSession(session: AuthSession) {
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
}

describe('App session expiry', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('redirects to login when stored session is already expired', () => {
    const session: AuthSession = {
      accessToken: 'token',
      expiresAt: Date.now() - 1000,
      user: {
        userId: 101,
        role: 'user',
        source: 'jwt',
        privileged: false,
      },
    }
    storeSession(session)
    window.history.pushState({}, '', '/')

    render(<App />)

    expect(screen.getByText('登录工作台')).toBeInTheDocument()
    expect(screen.getByText('会话已过期，请重新登录。')).toBeInTheDocument()
  })

  it('redirects non-privileged users away from feedback route', () => {
    const session: AuthSession = {
      accessToken: 'token',
      expiresAt: Date.now() + 60_000,
      user: {
        userId: 101,
        role: 'user',
        source: 'jwt',
        privileged: false,
      },
    }
    storeSession(session)
    window.history.pushState({}, '', '/feedback')

    render(<App />)

    expect(screen.getByText('Dashboard Mock')).toBeInTheDocument()
    expect(screen.queryByText('FeedbackForm Mock')).not.toBeInTheDocument()
  })

  it('allows privileged users to access feedback route', () => {
    const session: AuthSession = {
      accessToken: 'token',
      expiresAt: Date.now() + 60_000,
      user: {
        userId: 101,
        role: 'matchmaker',
        source: 'jwt',
        privileged: true,
      },
    }
    storeSession(session)
    window.history.pushState({}, '', '/feedback')

    render(<App />)

    expect(screen.getByText('FeedbackForm Mock')).toBeInTheDocument()
  })
})
