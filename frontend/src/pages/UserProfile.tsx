import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api, type ProfileUpdate, type PreferenceCreate, type ConstraintCreate, type ObservationTagCreate } from '../api/client'

// --- Inline add forms ---

function AddPreferenceForm({ userId, onDone }: { userId: number; onDone: () => void }) {
  const [dimension, setDimension] = useState('age')
  const [operator, setOperator] = useState('between')
  const [valueJson, setValueJson] = useState('')
  const [priority, setPriority] = useState('prefer')

  const mutation = useMutation({
    mutationFn: () => {
      const data: PreferenceCreate = {
        dimension, operator,
        value_json: valueJson ? JSON.parse(valueJson) : undefined,
        priority_level: priority,
      }
      return api.profile.addPreference(userId, data)
    },
    onSuccess: onDone,
  })

  return (
    <div className="border rounded p-3 bg-gray-50 space-y-2 text-sm">
      <div className="grid grid-cols-2 gap-2">
        <select value={dimension} onChange={(e) => setDimension(e.target.value)} className="border rounded px-2 py-1">
          {['age', 'height', 'city', 'education', 'marital_status'].map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <select value={operator} onChange={(e) => setOperator(e.target.value)} className="border rounded px-2 py-1">
          {['between', 'in', 'not_in', 'gte', 'lte', 'eq'].map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
      <input type="text" value={valueJson} onChange={(e) => setValueJson(e.target.value)}
        className="w-full border rounded px-2 py-1" placeholder='值 JSON, 如 {"min":25,"max":35}' />
      <select value={priority} onChange={(e) => setPriority(e.target.value)} className="border rounded px-2 py-1">
        {['must', 'prefer', 'avoid'].map(p => <option key={p} value={p}>{p}</option>)}
      </select>
      <div className="flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending}
          className="px-3 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50">
          {mutation.isPending ? '...' : '添加'}
        </button>
        <button onClick={onDone} className="px-3 py-1 bg-gray-300 rounded text-xs hover:bg-gray-400">取消</button>
      </div>
      {mutation.isError && <p className="text-red-600 text-xs">{(mutation.error as Error).message}</p>}
    </div>
  )
}

function AddConstraintForm({ userId, onDone }: { userId: number; onDone: () => void }) {
  const [tagCode, setTagCode] = useState('')
  const [tagType, setTagType] = useState('block')
  const [appliesToField, setAppliesToField] = useState('age')

  const mutation = useMutation({
    mutationFn: () => {
      const data: ConstraintCreate = { tag_code: tagCode, tag_type: tagType, applies_to_field: appliesToField }
      return api.profile.addConstraint(userId, data)
    },
    onSuccess: onDone,
  })

  return (
    <div className="border rounded p-3 bg-gray-50 space-y-2 text-sm">
      <input type="text" value={tagCode} onChange={(e) => setTagCode(e.target.value)}
        className="w-full border rounded px-2 py-1" placeholder="标签代码, 如 no_smoking" maxLength={64} />
      <div className="grid grid-cols-2 gap-2">
        <select value={tagType} onChange={(e) => setTagType(e.target.value)} className="border rounded px-2 py-1">
          {['block', 'verify'].map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={appliesToField} onChange={(e) => setAppliesToField(e.target.value)} className="border rounded px-2 py-1">
          {['age', 'height_cm', 'city_code', 'education_level', 'marital_status', 'occupation', 'smoking_status', 'drinking_status', 'pet_status'].map(f =>
            <option key={f} value={f}>{f}</option>
          )}
        </select>
      </div>
      <div className="flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !tagCode}
          className="px-3 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50">
          {mutation.isPending ? '...' : '添加'}
        </button>
        <button onClick={onDone} className="px-3 py-1 bg-gray-300 rounded text-xs hover:bg-gray-400">取消</button>
      </div>
      {mutation.isError && <p className="text-red-600 text-xs">{(mutation.error as Error).message}</p>}
    </div>
  )
}

function AddObservationTagForm({ userId, onDone }: { userId: number; onDone: () => void }) {
  const [tagCode, setTagCode] = useState('')
  const [tagValue, setTagValue] = useState('')
  const [confidence, setConfidence] = useState(80)

  const mutation = useMutation({
    mutationFn: () => {
      const data: ObservationTagCreate = {
        tag_code: tagCode,
        tag_value: tagValue || undefined,
        confidence,
        observer_type: 'matchmaker',
      }
      return api.profile.addObservationTag(userId, data)
    },
    onSuccess: onDone,
  })

  return (
    <div className="border rounded p-3 bg-gray-50 space-y-2 text-sm">
      <input type="text" value={tagCode} onChange={(e) => setTagCode(e.target.value)}
        className="w-full border rounded px-2 py-1" placeholder="标签代码, 如 personality_cheerful" maxLength={64} />
      <input type="text" value={tagValue} onChange={(e) => setTagValue(e.target.value)}
        className="w-full border rounded px-2 py-1" placeholder="标签值 (可选)" maxLength={64} />
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-600">置信度:</label>
        <input type="number" value={confidence} onChange={(e) => setConfidence(Number(e.target.value))}
          className="w-20 border rounded px-2 py-1" min={0} max={100} />
      </div>
      <div className="flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !tagCode}
          className="px-3 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50">
          {mutation.isPending ? '...' : '添加'}
        </button>
        <button onClick={onDone} className="px-3 py-1 bg-gray-300 rounded text-xs hover:bg-gray-400">取消</button>
      </div>
      {mutation.isError && <p className="text-red-600 text-xs">{(mutation.error as Error).message}</p>}
    </div>
  )
}

// --- Main component ---

export default function UserProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const fallbackUserId = session?.user.userId ?? 0
  const userId = Number(id || fallbackUserId)

  const [editing, setEditing] = useState(false)
  const [editData, setEditData] = useState<ProfileUpdate>({})
  const [showAddPreference, setShowAddPreference] = useState(false)
  const [showAddConstraint, setShowAddConstraint] = useState(false)
  const [showAddTag, setShowAddTag] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['profile', userId],
    queryFn: () => api.profile.get(userId),
    enabled: userId > 0,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['profile', userId] })

  const updateMutation = useMutation({
    mutationFn: (d: ProfileUpdate) => api.profile.update(userId, d),
    onSuccess: () => { setEditing(false); invalidate() },
  })

  const deletePreferenceMutation = useMutation({
    mutationFn: (prefId: number) => api.profile.deletePreference(userId, prefId),
    onSuccess: invalidate,
  })
  const deleteConstraintMutation = useMutation({
    mutationFn: (cId: number) => api.profile.deleteConstraint(userId, cId),
    onSuccess: invalidate,
  })
  const deleteTagMutation = useMutation({
    mutationFn: (tagId: number) => api.profile.deleteObservationTag(userId, tagId),
    onSuccess: invalidate,
  })

  const generateMutation = useMutation({
    mutationFn: () => api.recommendation.generate({ requesterUserId: userId }),
    onSuccess: () => navigate(`/recommendation/${userId}`),
  })

  if (!userId) return <div className="p-6 text-red-600">缺少有效的用户 ID</div>
  if (isLoading) return <div className="p-6">加载中...</div>
  if (error) return <div className="p-6 text-red-600">{error instanceof Error ? error.message : '加载失败'}</div>
  if (!data) return null

  const { profile, preferences, constraints, tags } = data

  const startEdit = () => {
    setEditData({
      gender: profile?.gender ?? undefined,
      age: profile?.age ?? undefined,
      height_cm: profile?.height_cm ?? undefined,
      city_code: profile?.city_code ?? undefined,
      education_level: profile?.education_level ?? undefined,
      marital_status: profile?.marital_status ?? undefined,
      occupation: profile?.occupation ?? undefined,
      smoking_status: profile?.smoking_status ?? undefined,
      drinking_status: profile?.drinking_status ?? undefined,
      pet_status: profile?.pet_status ?? undefined,
    })
    setEditing(true)
  }

  const handleFieldChange = (field: keyof ProfileUpdate, value: string | number | undefined) => {
    setEditData((prev) => ({ ...prev, [field]: value === '' ? undefined : value }))
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">&larr; 返回</button>
        <h1 className="text-2xl font-bold mb-6">用户画像 #{userId}</h1>

        {/* Basic profile */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold">基础资料</h2>
            {!editing && (
              <button onClick={startEdit} className="text-sm text-blue-600 hover:underline">编辑</button>
            )}
          </div>

          {editing ? (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-500 mb-1">性别</label>
                  <select value={editData.gender ?? ''} onChange={(e) => handleFieldChange('gender', e.target.value)} className="w-full border rounded px-2 py-1">
                    <option value="">-</option>
                    <option value="male">male</option>
                    <option value="female">female</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">年龄</label>
                  <input type="number" value={editData.age ?? ''} onChange={(e) => handleFieldChange('age', e.target.value ? Number(e.target.value) : undefined)}
                    className="w-full border rounded px-2 py-1" min={18} max={120} />
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">身高 (cm)</label>
                  <input type="number" value={editData.height_cm ?? ''} onChange={(e) => handleFieldChange('height_cm', e.target.value ? Number(e.target.value) : undefined)}
                    className="w-full border rounded px-2 py-1" min={100} max={250} />
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">城市</label>
                  <input type="text" value={editData.city_code ?? ''} onChange={(e) => handleFieldChange('city_code', e.target.value)}
                    className="w-full border rounded px-2 py-1" maxLength={32} />
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">学历</label>
                  <input type="text" value={editData.education_level ?? ''} onChange={(e) => handleFieldChange('education_level', e.target.value)}
                    className="w-full border rounded px-2 py-1" maxLength={32} />
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">婚史</label>
                  <input type="text" value={editData.marital_status ?? ''} onChange={(e) => handleFieldChange('marital_status', e.target.value)}
                    className="w-full border rounded px-2 py-1" maxLength={32} />
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">职业</label>
                  <input type="text" value={editData.occupation ?? ''} onChange={(e) => handleFieldChange('occupation', e.target.value)}
                    className="w-full border rounded px-2 py-1" maxLength={64} />
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">吸烟</label>
                  <select value={editData.smoking_status ?? ''} onChange={(e) => handleFieldChange('smoking_status', e.target.value)} className="w-full border rounded px-2 py-1">
                    <option value="">-</option>
                    {['yes', 'no', 'sometimes', 'unknown'].map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">饮酒</label>
                  <select value={editData.drinking_status ?? ''} onChange={(e) => handleFieldChange('drinking_status', e.target.value)} className="w-full border rounded px-2 py-1">
                    <option value="">-</option>
                    {['yes', 'no', 'sometimes', 'unknown'].map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-500 mb-1">宠物</label>
                  <select value={editData.pet_status ?? ''} onChange={(e) => handleFieldChange('pet_status', e.target.value)} className="w-full border rounded px-2 py-1">
                    <option value="">-</option>
                    {['has_cat', 'has_dog', 'has_pet', 'no_pet', 'unknown'].map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={() => updateMutation.mutate(editData)} disabled={updateMutation.isPending}
                  className="px-4 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
                  {updateMutation.isPending ? '保存中...' : '保存'}
                </button>
                <button onClick={() => setEditing(false)} className="px-4 py-1 bg-gray-300 rounded text-sm hover:bg-gray-400">取消</button>
              </div>
              {updateMutation.isError && <p className="text-red-600 text-xs">{(updateMutation.error as Error).message}</p>}
            </div>
          ) : (
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-gray-500">性别</dt><dd>{profile?.gender ?? '-'}</dd>
              <dt className="text-gray-500">年龄</dt><dd>{profile?.age ?? '-'}</dd>
              <dt className="text-gray-500">身高</dt><dd>{profile?.height_cm ? `${profile.height_cm} cm` : '-'}</dd>
              <dt className="text-gray-500">城市</dt><dd>{profile?.city_code ?? '-'}</dd>
              <dt className="text-gray-500">学历</dt><dd>{profile?.education_level ?? '-'}</dd>
              <dt className="text-gray-500">婚史</dt><dd>{profile?.marital_status ?? '-'}</dd>
              <dt className="text-gray-500">职业</dt><dd>{profile?.occupation ?? '-'}</dd>
              <dt className="text-gray-500">吸烟</dt><dd>{profile?.smoking_status ?? '-'}</dd>
              <dt className="text-gray-500">饮酒</dt><dd>{profile?.drinking_status ?? '-'}</dd>
              <dt className="text-gray-500">宠物</dt><dd>{profile?.pet_status ?? '-'}</dd>
            </dl>
          )}
        </div>

        {/* Preferences */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold">偏好条件</h2>
            {!showAddPreference && (
              <button onClick={() => setShowAddPreference(true)} className="text-sm text-blue-600 hover:underline">+ 新增</button>
            )}
          </div>
          <ul className="space-y-2 text-sm">
            {preferences.map((p) => (
              <li key={p.preference_id} className="flex justify-between items-center">
                <span>{p.dimension}: {p.operator} {JSON.stringify(p.value_json)} <span className="text-gray-400">({p.priority_level})</span></span>
                <button onClick={() => deletePreferenceMutation.mutate(p.preference_id)}
                  disabled={deletePreferenceMutation.isPending}
                  className="text-red-500 hover:text-red-700 text-xs">删除</button>
              </li>
            ))}
            {preferences.length === 0 && !showAddPreference && <li className="text-gray-500">暂无</li>}
          </ul>
          {showAddPreference && (
            <div className="mt-3">
              <AddPreferenceForm userId={userId} onDone={() => { setShowAddPreference(false); invalidate() }} />
            </div>
          )}
        </div>

        {/* Constraints */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold">禁忌约束</h2>
            {!showAddConstraint && (
              <button onClick={() => setShowAddConstraint(true)} className="text-sm text-blue-600 hover:underline">+ 新增</button>
            )}
          </div>
          <ul className="space-y-2 text-sm">
            {constraints.map((c) => (
              <li key={c.constraint_id} className="flex justify-between items-center">
                <span><span className="font-medium">{c.tag_code}</span> ({c.tag_type}) - {c.applies_to_field}</span>
                <button onClick={() => deleteConstraintMutation.mutate(c.constraint_id)}
                  disabled={deleteConstraintMutation.isPending}
                  className="text-red-500 hover:text-red-700 text-xs">删除</button>
              </li>
            ))}
            {constraints.length === 0 && !showAddConstraint && <li className="text-gray-500">暂无</li>}
          </ul>
          {showAddConstraint && (
            <div className="mt-3">
              <AddConstraintForm userId={userId} onDone={() => { setShowAddConstraint(false); invalidate() }} />
            </div>
          )}
        </div>

        {/* Observation Tags */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold">观察标签</h2>
            {!showAddTag && (
              <button onClick={() => setShowAddTag(true)} className="text-sm text-blue-600 hover:underline">+ 新增</button>
            )}
          </div>
          <ul className="space-y-2 text-sm">
            {tags.map((t) => (
              <li key={t.tag_id} className="flex justify-between items-center">
                <span>{t.tag_code}: {t.tag_value ?? '-'} <span className="text-gray-400">(置信度 {t.confidence}%)</span></span>
                <button onClick={() => deleteTagMutation.mutate(t.tag_id)}
                  disabled={deleteTagMutation.isPending}
                  className="text-red-500 hover:text-red-700 text-xs">删除</button>
              </li>
            ))}
            {tags.length === 0 && !showAddTag && <li className="text-gray-500">暂无</li>}
          </ul>
          {showAddTag && (
            <div className="mt-3">
              <AddObservationTagForm userId={userId} onDone={() => { setShowAddTag(false); invalidate() }} />
            </div>
          )}
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
