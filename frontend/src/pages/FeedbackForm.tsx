import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'

export default function FeedbackForm() {
  const navigate = useNavigate()
  const { session } = useAuth()
  const [userAId, setUserAId] = useState(session?.user.userId ?? 0)
  const [userBId, setUserBId] = useState(0)
  const [willingnessA, setWillingnessA] = useState('yes')
  const [willingnessB, setWillingnessB] = useState('yes')
  const [memoText, setMemoText] = useState('')

  const mutation = useMutation({
    mutationFn: () => api.feedback.recordMeeting({
      userAId,
      userBId,
      willingnessA: willingnessA,
      willingnessB: willingnessB,
      memoText,
    }),
    onSuccess: () => {
      alert('反馈已提交')
      setMemoText('')
      setUserBId(0)
    },
  })

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-2xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">← 返回</button>
        <h1 className="text-2xl font-bold mb-6">反馈录入</h1>

        <form onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">用户 A ID</label>
            <input type="number" value={userAId} onChange={(e) => setUserAId(parseInt(e.target.value, 10) || 0)} className="w-full border rounded px-3 py-2" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">用户 B ID</label>
            <input type="number" value={userBId || ''} onChange={(e) => setUserBId(parseInt(e.target.value, 10) || 0)} className="w-full border rounded px-3 py-2" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">A 方意愿</label>
            <select value={willingnessA} onChange={(e) => setWillingnessA(e.target.value)} className="w-full border rounded px-3 py-2">
              <option value="yes">继续</option>
              <option value="no">不继续</option>
              <option value="maybe">考虑</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">B 方意愿</label>
            <select value={willingnessB} onChange={(e) => setWillingnessB(e.target.value)} className="w-full border rounded px-3 py-2">
              <option value="yes">继续</option>
              <option value="no">不继续</option>
              <option value="maybe">考虑</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Memo</label>
            <textarea value={memoText} onChange={(e) => setMemoText(e.target.value)} rows={4} className="w-full border rounded px-3 py-2" placeholder="见面过程、感受、建议..." />
          </div>
          <button type="submit" disabled={mutation.isPending} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
            {mutation.isPending ? '提交中...' : '提交'}
          </button>
        </form>
      </div>
    </div>
  )
}
