import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api, ApproveExtractionResponse } from '../api/client'

const ACTION_LABELS: Record<string, string> = {
  create_observation_tag: '写入观察标签',
  create_constraint: '写入约束规则',
  create_verify_task: '创建待核实任务',
  none: '无操作',
}

const ACTION_COLORS: Record<string, string> = {
  create_observation_tag: 'bg-blue-100 text-blue-700',
  create_constraint: 'bg-red-100 text-red-700',
  create_verify_task: 'bg-amber-100 text-amber-700',
  none: 'bg-gray-100 text-gray-600',
}

export default function AIExtractionReview() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const [entityType, setEntityType] = useState('memo')
  const [entityId, setEntityId] = useState<number>(0)
  const [statusFilter, setStatusFilter] = useState<string>('suggested')
  const [lastApproveResult, setLastApproveResult] = useState<ApproveExtractionResponse | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['aiExtraction', entityType, entityId, statusFilter],
    queryFn: () => api.aiExtraction.get(entityType, entityId, statusFilter || undefined),
    enabled: entityId > 0,
  })

  const approveMutation = useMutation({
    mutationFn: (id: number) => api.aiExtraction.approve(id, session?.user.userId),
    onSuccess: (res) => {
      setLastApproveResult(res)
      queryClient.invalidateQueries({ queryKey: ['aiExtraction', entityType, entityId] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (id: number) => api.aiExtraction.reject(id, session?.user.userId),
    onSuccess: () => {
      setLastApproveResult(null)
      queryClient.invalidateQueries({ queryKey: ['aiExtraction', entityType, entityId] })
    },
  })

  if (isLoading) return <div className="p-6">加载中...</div>
  if (error) return <div className="p-6 text-red-600">{error instanceof Error ? error.message : '加载失败'}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">&larr; 返回</button>
        <h1 className="text-2xl font-bold mb-6">AI 抽取审核</h1>

        <div className="mb-6 grid gap-4 rounded-lg border bg-white p-4 md:grid-cols-[180px_1fr_140px]">
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
          <div>
            <label className="mb-1 block text-sm font-medium">状态筛选</label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-full rounded border px-3 py-2">
              <option value="suggested">待审核</option>
              <option value="approved">已通过</option>
              <option value="rejected">已驳回</option>
              <option value="">全部</option>
            </select>
          </div>
        </div>

        {/* Writeback result banner */}
        {lastApproveResult && lastApproveResult.appliedAction !== 'none' && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
            审核通过 #{lastApproveResult.extractionId}，已{ACTION_LABELS[lastApproveResult.appliedAction] || lastApproveResult.appliedAction}
            {lastApproveResult.createdObservationTagId && ` (tag #${lastApproveResult.createdObservationTagId})`}
            {lastApproveResult.createdConstraintId && ` (constraint #${lastApproveResult.createdConstraintId})`}
            {lastApproveResult.createdVerifyTaskId && ` (task #${lastApproveResult.createdVerifyTaskId})`}
          </div>
        )}

        {entityId <= 0 ? (
          <p className="text-gray-500">先输入要查询的实体 ID。</p>
        ) : null}

        {entityId > 0 && (!data || data.length === 0) && (
          <p className="text-gray-500">暂无{statusFilter === 'suggested' ? '待审核' : ''}抽取记录</p>
        )}

        <ul className="space-y-4">
          {data?.map((e) => (
            <li key={e.extraction_id} className="bg-white rounded-lg shadow p-4">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{e.extracted_label}: {e.extracted_value}</p>
                    {e.extraction_type && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                        {e.extraction_type}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 mt-1">置信度: {e.confidence}%</p>
                  {e.evidence_text && <p className="text-sm mt-2 italic text-gray-600">证据: {e.evidence_text}</p>}
                  {/* Suggested action hint */}
                  {e.suggested_action && e.suggested_action !== 'none' && e.extraction_status === 'suggested' && (
                    <p className="mt-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${ACTION_COLORS[e.suggested_action] || ''}`}>
                        通过后将: {ACTION_LABELS[e.suggested_action] || e.suggested_action}
                      </span>
                    </p>
                  )}
                </div>
                {e.extraction_status === 'suggested' && (
                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => approveMutation.mutate(e.extraction_id)}
                      disabled={approveMutation.isPending || rejectMutation.isPending}
                      className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
                    >通过</button>
                    <button
                      onClick={() => rejectMutation.mutate(e.extraction_id)}
                      disabled={approveMutation.isPending || rejectMutation.isPending}
                      className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 disabled:opacity-50"
                    >驳回</button>
                  </div>
                )}
                {e.extraction_status !== 'suggested' && (
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    e.extraction_status === 'approved' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {e.extraction_status === 'approved' ? '已通过' : '已驳回'}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
