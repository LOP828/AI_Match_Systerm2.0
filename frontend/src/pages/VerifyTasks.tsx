import { useState } from 'react'
import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'

const VERIFY_FIELD_LABELS: Record<string, string> = {
  age: 'Age',
  height_cm: 'Height (cm)',
  city_code: 'City code',
  education_level: 'Education level',
  marital_status: 'Marital status',
  occupation: 'Occupation',
  smoking_status: 'Smoking status',
  drinking_status: 'Drinking status',
  pet_status: 'Pet status',
}

const VERIFY_FIELD_OPTIONS: Record<string, string[]> = {
  smoking_status: ['yes', 'no', 'sometimes', 'unknown'],
  drinking_status: ['yes', 'no', 'sometimes', 'unknown'],
  pet_status: ['has_cat', 'has_dog', 'has_pet', 'no_pet', 'unknown'],
  education_level: ['high_school', 'bachelor', 'master', 'phd'],
}

const VERIFY_FIELD_PLACEHOLDERS: Record<string, string> = {
  age: 'Enter the confirmed age',
  height_cm: 'Enter the confirmed height',
  city_code: 'Enter the confirmed city code',
  education_level: 'Select the confirmed education level',
  marital_status: 'Enter the confirmed marital status',
  occupation: 'Enter the confirmed occupation',
  smoking_status: 'Select the confirmed smoking status',
  drinking_status: 'Select the confirmed drinking status',
  pet_status: 'Select the confirmed pet status',
}

const NUMERIC_VERIFY_FIELDS = new Set(['age', 'height_cm'])

function getDraftValue(taskId: number, verifyField: string, draftValues: Record<number, string>): string {
  if (taskId in draftValues) {
    return draftValues[taskId]
  }

  const options = VERIFY_FIELD_OPTIONS[verifyField]
  return options ? options[0] : ''
}

export default function VerifyTasks() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const [requesterInput, setRequesterInput] = useState('')
  const [draftValues, setDraftValues] = useState<Record<number, string>>({})
  const defaultRequesterUserId = session?.user.userId ?? 0
  const requesterUserId = Number(requesterInput) || defaultRequesterUserId

  const { data, isLoading, error } = useQuery({
    queryKey: ['verifyTasks', requesterUserId],
    queryFn: () => api.verifyTasks.get(requesterUserId, 'pending'),
    enabled: requesterUserId > 0,
  })

  const confirmMutation = useMutation({
    mutationFn: ({ taskId, value }: { taskId: number; value: string }) =>
      api.verifyTasks.confirm(taskId, { confirmedValue: value }),
    onSuccess: (_result, variables) => {
      setDraftValues((current) => {
        const next = { ...current }
        delete next[variables.taskId]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['verifyTasks', requesterUserId] })
    },
  })

  function handleDraftChange(taskId: number) {
    return (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const { value } = event.target
      setDraftValues((current) => ({
        ...current,
        [taskId]: value,
      }))
    }
  }

  if (!requesterUserId) return <div className="p-6 text-red-600">Missing requester user id.</div>
  if (isLoading) return <div className="p-6">Loading tasks...</div>
  if (error) return <div className="p-6 text-red-600">{error instanceof Error ? error.message : 'Failed to load tasks.'}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-4xl">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">
          Back
        </button>
        <h1 className="mb-6 text-2xl font-bold">Pending verification tasks</h1>

        <div className="mb-6 rounded-lg border bg-white p-4">
          <label className="mb-1 block text-sm font-medium">Requester user id</label>
          <input
            type="number"
            value={requesterInput || String(defaultRequesterUserId || '')}
            onChange={(event) => setRequesterInput(event.target.value)}
            className="w-full rounded border px-3 py-2 md:w-64"
          />
        </div>

        {(!data || data.length === 0) && <p className="text-gray-500">No pending tasks.</p>}

        <ul className="space-y-4">
          {data?.map((task) => {
            const options = VERIFY_FIELD_OPTIONS[task.verify_field]
            const value = getDraftValue(task.task_id, task.verify_field, draftValues)
            const trimmedValue = value.trim()
            const inputId = `verify-value-${task.task_id}`
            const ariaLabel = `confirmed-value-${task.task_id}`
            const isNumericField = NUMERIC_VERIFY_FIELDS.has(task.verify_field)

            return (
              <li key={task.task_id} className="rounded-lg bg-white p-4 shadow">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="font-medium">
                      Candidate #{task.candidate_user_id} - {VERIFY_FIELD_LABELS[task.verify_field] ?? task.verify_field}
                    </p>
                    <p className="mt-1 text-sm text-gray-500">{task.trigger_reason}</p>
                  </div>

                  <div className="w-full max-w-sm">
                    <label htmlFor={inputId} className="mb-2 block text-sm font-medium text-gray-700">
                      Confirmed value
                    </label>
                    {options ? (
                      <select
                        id={inputId}
                        aria-label={ariaLabel}
                        value={value}
                        onChange={handleDraftChange(task.task_id)}
                        className="w-full rounded border px-3 py-2"
                      >
                        {options.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        id={inputId}
                        aria-label={ariaLabel}
                        type={isNumericField ? 'number' : 'text'}
                        inputMode={isNumericField ? 'numeric' : undefined}
                        min={task.verify_field === 'age' ? 18 : task.verify_field === 'height_cm' ? 100 : undefined}
                        value={value}
                        onChange={handleDraftChange(task.task_id)}
                        placeholder={VERIFY_FIELD_PLACEHOLDERS[task.verify_field] ?? 'Enter the confirmed value'}
                        className="w-full rounded border px-3 py-2"
                      />
                    )}

                    <button
                      onClick={() => confirmMutation.mutate({ taskId: task.task_id, value: trimmedValue })}
                      disabled={confirmMutation.isPending || trimmedValue.length === 0}
                      className="mt-3 rounded bg-green-600 px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Confirm
                    </button>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
