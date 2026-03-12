import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api, type InteractionHistoryItem, type FeedbackSignals } from '../api/client'

function RatingSelect({ label, value, onChange }: { label: string; value: number | undefined; onChange: (v: number | undefined) => void }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(value === n ? undefined : n)}
            className={`w-10 h-10 rounded-full border-2 text-sm font-bold ${value === n ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'}`}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  )
}

function SignalsCard({ signals }: { signals: FeedbackSignals }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-2">
      <h3 className="font-semibold text-blue-800">反馈信号汇总</h3>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>见面次数: <span className="font-medium">{signals.totalMeetings}</span></div>
        <div>继续率: <span className="font-medium">{signals.continueRate != null ? `${(signals.continueRate * 100).toFixed(0)}%` : '-'}</span></div>
        <div>聊天流畅度: <span className="font-medium">{signals.avgConversationSmoothness?.toFixed(1) ?? '-'}</span></div>
        <div>外貌接受度: <span className="font-medium">{signals.avgAppearanceAcceptance?.toFixed(1) ?? '-'}</span></div>
        <div>三观契合度: <span className="font-medium">{signals.avgValuesAlignment?.toFixed(1) ?? '-'}</span></div>
        <div>常见拒绝原因: <span className="font-medium">{signals.topRejectReasons.length > 0 ? signals.topRejectReasons.join(', ') : '-'}</span></div>
      </div>
    </div>
  )
}

function HistoryList({ items }: { items: InteractionHistoryItem[] }) {
  if (items.length === 0) return <p className="text-gray-500 text-sm">暂无历史记录</p>

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.event_id} className="border rounded-lg p-3 bg-white text-sm">
          <div className="flex justify-between mb-1">
            <span className="font-medium">#{item.event_id} · {item.user_a_id} ↔ {item.user_b_id}</span>
            <span className="text-gray-500">{item.event_time ?? item.created_at ?? ''}</span>
          </div>
          <div className="flex gap-4 text-gray-600">
            <span>A意愿: {item.willingness_a}</span>
            <span>B意愿: {item.willingness_b}</span>
          </div>
          {(item.conversation_smoothness || item.appearance_acceptance || item.values_alignment) && (
            <div className="flex gap-4 text-gray-600 mt-1">
              {item.conversation_smoothness && <span>流畅:{item.conversation_smoothness}</span>}
              {item.appearance_acceptance && <span>外貌:{item.appearance_acceptance}</span>}
              {item.values_alignment && <span>三观:{item.values_alignment}</span>}
            </div>
          )}
          {(item.reject_reason_primary || item.reject_reason_secondary) && (
            <div className="text-red-600 mt-1">
              拒绝原因: {[item.reject_reason_primary, item.reject_reason_secondary].filter(Boolean).join(', ')}
            </div>
          )}
          {item.memo_text && <p className="text-gray-700 mt-1 italic">"{item.memo_text}"</p>}
        </div>
      ))}
    </div>
  )
}

export default function FeedbackForm() {
  const navigate = useNavigate()
  const { session } = useAuth()
  const [userAId, setUserAId] = useState(session?.user.userId ?? 0)
  const [userBId, setUserBId] = useState(0)
  const [willingnessA, setWillingnessA] = useState('yes')
  const [willingnessB, setWillingnessB] = useState('yes')
  const [conversationSmoothness, setConversationSmoothness] = useState<number | undefined>()
  const [appearanceAcceptance, setAppearanceAcceptance] = useState<number | undefined>()
  const [valuesAlignment, setValuesAlignment] = useState<number | undefined>()
  const [rejectReasonPrimary, setRejectReasonPrimary] = useState('')
  const [rejectReasonSecondary, setRejectReasonSecondary] = useState('')
  const [memoText, setMemoText] = useState('')
  const [historyUserId, setHistoryUserId] = useState<number | undefined>()

  const mutation = useMutation({
    mutationFn: () => api.feedback.recordMeeting({
      userAId,
      userBId,
      willingnessA,
      willingnessB,
      conversationSmoothness,
      appearanceAcceptance,
      valuesAlignment,
      rejectReasonPrimary: rejectReasonPrimary || undefined,
      rejectReasonSecondary: rejectReasonSecondary || undefined,
      memoText,
    }),
    onSuccess: () => {
      alert('反馈已提交')
      setMemoText('')
      setUserBId(0)
      setConversationSmoothness(undefined)
      setAppearanceAcceptance(undefined)
      setValuesAlignment(undefined)
      setRejectReasonPrimary('')
      setRejectReasonSecondary('')
    },
  })

  const historyQuery = useQuery({
    queryKey: ['feedback-history', historyUserId],
    queryFn: () => api.feedback.getUserHistory(historyUserId!, 20),
    enabled: !!historyUserId,
  })

  const signalsQuery = useQuery({
    queryKey: ['feedback-signals', historyUserId],
    queryFn: () => api.feedback.getSignals(historyUserId!),
    enabled: !!historyUserId,
  })

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-2xl mx-auto">
        <button onClick={() => navigate('/')} className="mb-4 text-blue-600 hover:underline">&larr; 返回</button>
        <h1 className="text-2xl font-bold mb-6">反馈录入</h1>

        <form onSubmit={(e) => { e.preventDefault(); mutation.mutate() }} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">用户 A ID</label>
              <input type="number" value={userAId} onChange={(e) => setUserAId(parseInt(e.target.value, 10) || 0)} className="w-full border rounded px-3 py-2" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">用户 B ID</label>
              <input type="number" value={userBId || ''} onChange={(e) => setUserBId(parseInt(e.target.value, 10) || 0)} className="w-full border rounded px-3 py-2" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
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
          </div>

          <div className="border-t pt-4">
            <h2 className="text-lg font-semibold mb-3">结构化评分（可选）</h2>
            <div className="space-y-3">
              <RatingSelect label="聊天流畅度 (1-5)" value={conversationSmoothness} onChange={setConversationSmoothness} />
              <RatingSelect label="外貌接受度 (1-5)" value={appearanceAcceptance} onChange={setAppearanceAcceptance} />
              <RatingSelect label="三观契合度 (1-5)" value={valuesAlignment} onChange={setValuesAlignment} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">主要拒绝原因</label>
              <input type="text" value={rejectReasonPrimary} onChange={(e) => setRejectReasonPrimary(e.target.value)} className="w-full border rounded px-3 py-2" placeholder="如：外貌不合、距离太远..." maxLength={64} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">次要拒绝原因</label>
              <input type="text" value={rejectReasonSecondary} onChange={(e) => setRejectReasonSecondary(e.target.value)} className="w-full border rounded px-3 py-2" placeholder="可选" maxLength={64} />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Memo</label>
            <textarea value={memoText} onChange={(e) => setMemoText(e.target.value)} rows={4} className="w-full border rounded px-3 py-2" placeholder="见面过程、感受、建议..." />
          </div>
          <button type="submit" disabled={mutation.isPending} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
            {mutation.isPending ? '提交中...' : '提交'}
          </button>
        </form>

        {/* History & Signals Section */}
        <div className="mt-10 border-t pt-6">
          <h2 className="text-xl font-bold mb-4">反馈历史查询</h2>
          <div className="flex gap-2 items-end mb-4">
            <div>
              <label className="block text-sm font-medium mb-1">查询用户 ID</label>
              <input type="number" value={historyUserId ?? ''} onChange={(e) => setHistoryUserId(parseInt(e.target.value, 10) || undefined)} className="border rounded px-3 py-2 w-32" />
            </div>
          </div>

          {signalsQuery.data && <SignalsCard signals={signalsQuery.data} />}
          <div className="mt-4">
            {historyQuery.isLoading && <p className="text-gray-500">加载中...</p>}
            {historyQuery.data && <HistoryList items={historyQuery.data} />}
          </div>
        </div>
      </div>
    </div>
  )
}
