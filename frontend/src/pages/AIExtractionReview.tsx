import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'

export default function AIExtractionReview() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const [entityType, setEntityType] = useState('memo')
  const [entityId, setEntityId] = useState<number>(0)

  const { data, isLoading, error } = useQuery({
    queryKey: ['aiExtraction', entityType, entityId],
    queryFn: () => api.aiExtraction.get(entityType, entityId, 'suggested'),
    enabled: entityId > 0,
  })

  const approveMutation = useMutation({
    mutationFn: (id: number) => api.aiExtraction.approve(id, session?.user.userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['aiExtraction', entityType, entityId] }),
  })

  const rejectMutation = useMutation({
    mutationFn: (id: number) => api.aiExtraction.reject(id, session?.user.userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['aiExtraction', entityType, entityId] }),
  })

  if (isLoading) return <div className="p-6">加载中...</div>
  if (error) return <div className="p-6 text-red-600">{error instanceof Error ? error.message : '加载失败'}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">← 返回</button>
        <h1 className="text-2xl font-bold mb-6">AI 抽取审核</h1>

        <div className="mb-6 grid gap-4 rounded-lg border bg-white p-4 md:grid-cols-[180px_1fr]">
          <div>
            <label className="mb-1 block text-sm font-medium">实体类型</label>
            <select value={entityType} onChange={(event) => setEntityType(event.target.value)} className="w-full rounded border px-3 py-2">
              <option value="memo">memo</option>
              <option value="user">user</option>
              <option value="event">event</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">实体 ID</label>
            <input
              type="number"
              value={entityId || ''}
              onChange={(event) => setEntityId(Number(event.target.value) || 0)}
              className="w-full rounded border px-3 py-2"
              placeholder="输入待审核实体 ID"
            />
          </div>
        </div>

        {entityId <= 0 ? (
          <p className="text-gray-500">先输入要查询的实体 ID。</p>
        ) : null}

        {entityId > 0 && (!data || data.length === 0) && (
          <p className="text-gray-500">暂无待审核抽取（需先录入反馈 Memo 并触发 AI 抽取）</p>
        )}

        <ul className="space-y-4">
          {data?.map((e) => (
            <li key={e.extraction_id} className="bg-white rounded-lg shadow p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium">{e.extracted_label}: {e.extracted_value}</p>
                  <p className="text-sm text-gray-500 mt-1">置信度: {e.confidence}%</p>
                  {e.evidence_text && <p className="text-sm mt-2 italic">证据: {e.evidence_text}</p>}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => approveMutation.mutate(e.extraction_id)}
                    disabled={approveMutation.isPending || rejectMutation.isPending}
                    className="px-3 py-1 bg-green-600 text-white text-sm rounded"
                  >通过</button>
                  <button
                    onClick={() => rejectMutation.mutate(e.extraction_id)}
                    disabled={approveMutation.isPending || rejectMutation.isPending}
                    className="px-3 py-1 bg-red-600 text-white text-sm rounded"
                  >驳回</button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
