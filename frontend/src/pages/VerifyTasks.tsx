import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'

export default function VerifyTasks() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const [requesterUserId, setRequesterUserId] = useState<number>(session?.user.userId ?? 0)

  useEffect(() => {
    if (session?.user.userId) {
      setRequesterUserId(session.user.userId)
    }
  }, [session?.user.userId])

  const { data, isLoading, error } = useQuery({
    queryKey: ['verifyTasks', requesterUserId],
    queryFn: () => api.verifyTasks.get(requesterUserId, 'pending'),
    enabled: requesterUserId > 0,
  })

  const confirmMutation = useMutation({
    mutationFn: ({ taskId, value }: { taskId: number; value: string }) =>
      api.verifyTasks.confirm(taskId, { confirmedValue: value }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['verifyTasks', requesterUserId] }),
  })

  if (!requesterUserId) return <div className="p-6 text-red-600">缺少有效的 requesterUserId</div>
  if (isLoading) return <div className="p-6">加载中...</div>
  if (error) return <div className="p-6 text-red-600">{error instanceof Error ? error.message : '加载失败'}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">← 返回</button>
        <h1 className="text-2xl font-bold mb-6">待核实队列</h1>

        <div className="mb-6 rounded-lg border bg-white p-4">
          <label className="mb-1 block text-sm font-medium">目标请求用户 ID</label>
          <input
            type="number"
            value={requesterUserId}
            onChange={(event) => setRequesterUserId(Number(event.target.value) || 0)}
            className="w-full rounded border px-3 py-2 md:w-64"
          />
        </div>

        {(!data || data.length === 0) && (
          <p className="text-gray-500">暂无待核实任务</p>
        )}

        <ul className="space-y-4">
          {data?.map((t) => (
            <li key={t.task_id} className="bg-white rounded-lg shadow p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium">候选人 #{t.candidate_user_id} - {t.verify_field}</p>
                  <p className="text-sm text-gray-500 mt-1">{t.trigger_reason}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => confirmMutation.mutate({ taskId: t.task_id, value: 'yes' })}
                    disabled={confirmMutation.isPending}
                    className="px-3 py-1 bg-green-600 text-white text-sm rounded"
                  >确认是</button>
                  <button
                    onClick={() => confirmMutation.mutate({ taskId: t.task_id, value: 'no' })}
                    disabled={confirmMutation.isPending}
                    className="px-3 py-1 bg-red-600 text-white text-sm rounded"
                  >确认否</button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
