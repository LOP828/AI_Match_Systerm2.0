import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'

export default function RecommendationResults() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { session } = useAuth()
  const requesterId = Number(id || session?.user.userId || 0)

  const { data, isLoading, error } = useQuery({
    queryKey: ['recommendations', requesterId],
    queryFn: () => api.recommendation.get(requesterId),
    enabled: requesterId > 0,
  })

  if (!requesterId) return <div className="p-6 text-red-600">缺少有效的用户 ID</div>
  if (isLoading) return <div className="p-6">加载中...</div>
  if (error) return <div className="p-6 text-red-600">{error instanceof Error ? error.message : '加载失败'}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">← 返回</button>
        <h1 className="text-2xl font-bold mb-6">推荐结果 - 用户 #{requesterId}</h1>

        {(!data || data.length === 0) && (
          <p className="text-gray-500">暂无推荐快照，请先在用户画像页点击「生成推荐 TopN」</p>
        )}

        <ul className="space-y-4">
          {data?.map((s) => (
            <li key={s.rec_id} className="bg-white rounded-lg shadow p-4">
              <div className="flex justify-between">
                <span className="font-medium">候选人 #{s.candidate_user_id}</span>
                <span className="text-sm text-gray-500">{s.snapshot_stage}</span>
              </div>
              <div className="mt-2 text-sm text-gray-600">
                安全分: {s.safety_score} | 聊天分: {s.chat_score} | 综合分: {s.final_rank_score}
              </div>
              {s.verify_pending_count ? (
                <span className="inline-block mt-2 text-amber-600 text-sm">待核实 {s.verify_pending_count} 项</span>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
