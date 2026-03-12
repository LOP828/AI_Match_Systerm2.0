import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Dashboard() {
  const { session, logout, expiresSoon, secondsRemaining } = useAuth()
  const currentUserId = session?.user.userId ?? 0

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-gray-500">Workbench</p>
          <h1 className="text-2xl font-bold">红娘工作台</h1>
          <p className="mt-1 text-sm text-gray-600">
            当前用户 #{currentUserId} · 角色 {session?.user.role}
          </p>
        </div>
        <button onClick={() => logout()} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100">
          退出登录
        </button>
      </div>

      {expiresSoon ? (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          会话将在 {secondsRemaining ?? 0} 秒后过期。到期后会自动退出并跳回登录页。
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Link to={`/user/${currentUserId}`} className="block p-4 bg-white rounded-lg shadow hover:shadow-md border">
          <h3 className="font-medium">用户画像</h3>
          <p className="text-sm text-gray-500 mt-1">查看/编辑当前登录用户资料</p>
        </Link>
        <Link to={`/recommendation/${currentUserId}`} className="block p-4 bg-white rounded-lg shadow hover:shadow-md border">
          <h3 className="font-medium">推荐结果</h3>
          <p className="text-sm text-gray-500 mt-1">为当前登录用户生成推荐</p>
        </Link>
        {session?.user.privileged ? (
          <>
            <Link to="/feedback" className="block p-4 bg-white rounded-lg shadow hover:shadow-md border">
              <h3 className="font-medium">反馈录入</h3>
              <p className="text-sm text-gray-500 mt-1">记录见面反馈</p>
            </Link>
            <Link to="/verify-tasks" className="block p-4 bg-white rounded-lg shadow hover:shadow-md border">
              <h3 className="font-medium">待核实队列</h3>
              <p className="text-sm text-gray-500 mt-1">按目标用户查看和处理待核实任务</p>
            </Link>
            <Link to="/ai-extraction-review" className="block p-4 bg-white rounded-lg shadow hover:shadow-md border">
              <h3 className="font-medium">AI 审核</h3>
              <p className="text-sm text-gray-500 mt-1">按实体类型和 ID 审核 AI 抽取结果</p>
            </Link>
          </>
        ) : null}
      </div>
    </div>
  )
}
