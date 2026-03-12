import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'

type Stage = 'rough' | 'verified'

export default function RecommendationResults() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const requesterId = Number(id || session?.user.userId || 0)
  const [stage, setStage] = useState<Stage>('rough')
  const [regenerateInfo, setRegenerateInfo] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['recommendations', requesterId, stage],
    queryFn: () => api.recommendation.get(requesterId, stage),
    enabled: requesterId > 0,
  })

  const regenerateMutation = useMutation({
    mutationFn: () => api.recommendation.regenerate(requesterId),
    onSuccess: (res) => {
      setRegenerateInfo(`已根据 ${res.usedConfirmedVerifyTasks} 条已确认信息重新排序`)
      setStage('verified')
      queryClient.invalidateQueries({ queryKey: ['recommendations', requesterId] })
    },
  })

  if (!requesterId) return <div className="p-6 text-red-600">缺少有效的用户 ID</div>
  if (isLoading) return <div className="p-6">加载中...</div>
  if (error) return <div className="p-6 text-red-600">{error instanceof Error ? error.message : '加载失败'}</div>

  const stageExplanation = data?.[0]?.explanation_json as { usedConfirmedVerifyTasks?: number } | undefined

  const stages: { key: Stage; label: string }[] = [
    { key: 'rough', label: '粗排' },
    { key: 'verified', label: '核实后' },
  ]

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">&larr; 返回</button>
        <h1 className="text-2xl font-bold mb-4">推荐结果 - 用户 #{requesterId}</h1>

        {/* Stage tabs */}
        <div className="flex items-center gap-2 mb-4">
          {stages.map((s) => (
            <button
              key={s.key}
              onClick={() => { setStage(s.key); setRegenerateInfo(null) }}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                stage === s.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              {s.label}
            </button>
          ))}

          <button
            onClick={() => regenerateMutation.mutate()}
            disabled={regenerateMutation.isPending}
            className="ml-auto px-4 py-1.5 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
          >
            {regenerateMutation.isPending ? '排序中...' : '根据已核实信息重新排序'}
          </button>
        </div>

        {/* Info banner */}
        {regenerateInfo && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
            {regenerateInfo}
          </div>
        )}
        {regenerateMutation.isError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
            重新排序失败: {regenerateMutation.error instanceof Error ? regenerateMutation.error.message : '未知错误'}
          </div>
        )}
        {!regenerateInfo && stage === 'verified' && typeof stageExplanation?.usedConfirmedVerifyTasks === 'number' && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
            This rerank used {stageExplanation.usedConfirmedVerifyTasks} confirmed items.
          </div>
        )}

        {/* Current stage indicator */}
        <div className="mb-4 text-sm text-gray-500">
          当前阶段: <span className="font-medium text-gray-700">{stage === 'rough' ? '粗排 (rough)' : '核实后 (verified)'}</span>
        </div>

        {(!data || data.length === 0) && (
          <p className="text-gray-500">
            {stage === 'verified'
              ? '暂无核实后快照，请点击「根据已核实信息重新排序」生成'
              : '暂无推荐快照，请先在用户画像页点击「生成推荐 TopN」'}
          </p>
        )}

        <ul className="space-y-4">
          {data?.map((s) => (
            <li key={s.rec_id} className="bg-white rounded-lg shadow p-4">
              <div className="flex justify-between">
                <span className="font-medium">候选人 #{s.candidate_user_id}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  s.snapshot_stage === 'verified'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {s.snapshot_stage}
                </span>
              </div>
              <div className="mt-2 text-sm text-gray-600">
                安全分: {s.safety_score} | 聊天分: {s.chat_score} | 综合分: {s.final_rank_score}
              </div>
              <div className="mt-1 flex items-center gap-4 text-xs text-gray-400">
                {s.created_at && <span>生成时间: {s.created_at}</span>}
                {s.verify_pending_count ? (
                  <span className="text-amber-600">待核实 {s.verify_pending_count} 项</span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
