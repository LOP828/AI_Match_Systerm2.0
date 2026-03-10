import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import VerifyTasks from './VerifyTasks'

const getVerifyTasks = vi.fn()
const confirmVerifyTask = vi.fn()

vi.mock('../api/client', () => ({
  api: {
    verifyTasks: {
      get: (...args: unknown[]) => getVerifyTasks(...args),
      confirm: (...args: unknown[]) => confirmVerifyTask(...args),
    },
  },
}))

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    session: {
      user: {
        userId: 101,
        privileged: true,
      },
    },
  }),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <VerifyTasks />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('VerifyTasks', () => {
  beforeEach(() => {
    getVerifyTasks.mockReset()
    confirmVerifyTask.mockReset()
  })

  it('submits the typed numeric value for numeric verification fields', async () => {
    getVerifyTasks.mockResolvedValue([
      {
        task_id: 1,
        requester_user_id: 101,
        candidate_user_id: 202,
        verify_field: 'age',
        trigger_reason: 'Confirm the candidate age',
        task_status: 'pending',
      },
    ])
    confirmVerifyTask.mockResolvedValue({ success: true })

    renderPage()

    expect(await screen.findByText('Candidate #202 - Age')).toBeInTheDocument()
    expect(getVerifyTasks).toHaveBeenCalledWith(101, 'pending')

    const input = screen.getByLabelText('confirmed-value-1')
    await userEvent.type(input, '29')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => {
      expect(confirmVerifyTask).toHaveBeenCalledWith(1, { confirmedValue: '29' })
    })
  })

  it('submits the selected enumerated value for option-based verification fields', async () => {
    getVerifyTasks.mockResolvedValue([
      {
        task_id: 2,
        requester_user_id: 101,
        candidate_user_id: 303,
        verify_field: 'smoking_status',
        trigger_reason: 'Confirm the candidate smoking status',
        task_status: 'pending',
      },
    ])
    confirmVerifyTask.mockResolvedValue({ success: true })

    renderPage()

    const select = await screen.findByLabelText('confirmed-value-2')
    await userEvent.selectOptions(select, 'sometimes')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => {
      expect(confirmVerifyTask).toHaveBeenCalledWith(2, { confirmedValue: 'sometimes' })
    })
  })
})
