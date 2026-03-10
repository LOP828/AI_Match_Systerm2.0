import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { session, login, logoutReason, clearLogoutReason } = useAuth()
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const logoutReasonMessage =
    logoutReason === 'expired'
      ? '会话已过期，请重新登录。'
      : logoutReason === 'unauthorized'
        ? '登录状态已失效，请重新登录。'
        : logoutReason === 'invalid'
          ? '检测到损坏的登录状态，请重新登录。'
          : ''

  if (session) {
    const redirectTo = (location.state as { from?: string } | null)?.from || '/'
    return <Navigate to={redirectTo} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      await login(Number(userId), password)
      const redirectTo = (location.state as { from?: string } | null)?.from || '/'
      navigate(redirectTo, { replace: true })
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 px-6 py-10 text-slate-900">
      <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-[0.3em] text-slate-500">AI Match System</p>
        <h1 className="mt-3 text-3xl font-semibold">登录工作台</h1>
        <p className="mt-2 text-sm text-slate-600">使用已配置的用户凭证获取 Bearer Token，所有业务请求都会自动带上登录态。</p>

        {logoutReasonMessage ? (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <div className="flex items-center justify-between gap-4">
              <span>{logoutReasonMessage}</span>
              <button type="button" onClick={clearLogoutReason} className="text-xs font-medium text-amber-900 underline">
                关闭
              </button>
            </div>
          </div>
        ) : null}

        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm font-medium">用户 ID</label>
            <input
              type="number"
              inputMode="numeric"
              min="1"
              required
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-slate-950"
              placeholder="例如 101"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">密码</label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-slate-950"
              placeholder="输入账户密码"
            />
          </div>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-slate-950 px-4 py-2 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? '登录中...' : '登录'}
          </button>
        </form>
      </div>
    </div>
  )
}