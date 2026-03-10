import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
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

describe('App session expiry', () => {
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
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
    window.history.pushState({}, '', '/')

    render(<App />)

    expect(screen.getByText('登录工作台')).toBeInTheDocument()
    expect(screen.getByText('会话已过期，请重新登录。')).toBeInTheDocument()
  })
})