import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { AUTH_LOGOUT_REASON_KEY } from '../auth/session'
import LoginPage from './LoginPage'

describe('LoginPage', () => {
  it('shows and clears unauthorized logout reason', async () => {
    window.sessionStorage.setItem(AUTH_LOGOUT_REASON_KEY, 'unauthorized')

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/login']}>
          <LoginPage />
        </MemoryRouter>
      </AuthProvider>,
    )

    expect(screen.getByText('登录状态已失效，请重新登录。')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '关闭' }))

    expect(screen.queryByText('登录状态已失效，请重新登录。')).not.toBeInTheDocument()
  })
})