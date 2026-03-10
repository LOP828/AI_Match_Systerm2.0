import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'

export default function UserProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { session } = useAuth()
  const fallbackUserId = session?.user.userId ?? 0
  const userId = Number(id || fallbackUserId)

  const { data, isLoading, error } = useQuery({
    queryKey: ['profile', userId],
    queryFn: () => api.profile.get(userId),
    enabled: userId > 0,
  })

  const generateMutation = useMutation({
    mutationFn: () => api.recommendation.generate({ requesterUserId: userId }),
    onSuccess: () => {
      navigate(`/recommendation/${userId}`)
    },
  })

  if (!userId) return <div className="p-6 text-red-600">缺少有效的用户 ID</div>
  if (isLoading) return <div className="p-6">加载中...</div>
  if (error) return <div className="p-6 text-red-600">{error instanceof Error ? error.message : '加载失败'}</div>
  if (!data) return null

  const { profile, preferences, constraints, tags } = data

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">← 返回</button>
        <h1 className="text-2xl font-bold mb-6">用户画像 #{userId}</h1>

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="font-semibold mb-4">基础资料</h2>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-gray-500">年龄</dt><dd>{profile?.age ?? '-'}</dd>
            <dt className="text-gray-500">身高</dt><dd>{profile?.height_cm ?? '-'} cm</dd>
            <dt className="text-gray-500">城市</dt><dd>{profile?.city_code ?? '-'}</dd>
            <dt className="text-gray-500">学历</dt><dd>{profile?.education_level ?? '-'}</dd>
            <dt className="text-gray-500">婚史</dt><dd>{profile?.marital_status ?? '-'}</dd>
            <dt className="text-gray-500">职业</dt><dd>{profile?.occupation ?? '-'}</dd>
            <dt className="text-gray-500">吸烟</dt><dd>{profile?.smoking_status ?? '-'}</dd>
            <dt className="text-gray-500">饮酒</dt><dd>{profile?.drinking_status ?? '-'}</dd>
            <dt className="text-gray-500">宠物</dt><dd>{profile?.pet_status ?? '-'}</dd>
          </dl>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="font-semibold mb-4">偏好条件</h2>
          <ul className="space-y-2 text-sm">
            {preferences.map((p) => (
              <li key={p.preference_id}>{p.dimension}: {p.operator} {JSON.stringify(p.value_json)}</li>
            ))}
            {preferences.length === 0 && <li className="text-gray-500">暂无</li>}
          </ul>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="font-semibold mb-4">禁忌约束</h2>
          <ul className="space-y-2 text-sm">
            {constraints.map((c) => (
              <li key={c.constraint_id}><span className="font-medium">{c.tag_code}</span> ({c.tag_type}) - {c.applies_to_field}</li>
            ))}
            {constraints.length === 0 && <li className="text-gray-500">暂无</li>}
          </ul>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="font-semibold mb-4">观察标签</h2>
          <ul className="space-y-2 text-sm">
            {tags.map((t) => (
              <li key={t.tag_id}>{t.tag_code}: {t.tag_value} (置信度 {t.confidence}%)</li>
            ))}
            {tags.length === 0 && <li className="text-gray-500">暂无</li>}
          </ul>
        </div>

        <button
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {generateMutation.isPending ? '生成中...' : '生成推荐 TopN'}
        </button>
      </div>
    </div>
  )
}
