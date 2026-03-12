import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './auth/AuthContext'
import Dashboard from './pages/Dashboard'
import UserProfile from './pages/UserProfile'
import RecommendationResults from './pages/RecommendationResults'
import VerifyTasks from './pages/VerifyTasks'
import FeedbackForm from './pages/FeedbackForm'
import AIExtractionReview from './pages/AIExtractionReview'
import LoginPage from './pages/LoginPage'

const queryClient = new QueryClient()

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session } = useAuth()
  const location = useLocation()

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}

function PrivilegedRoute({ children }: { children: React.ReactNode }) {
  const { session } = useAuth()

  if (!session) {
    return <Navigate to="/login" replace />
  }
  if (!session.user.privileged) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/user/:id" element={<ProtectedRoute><UserProfile /></ProtectedRoute>} />
            <Route path="/recommendation/:id" element={<ProtectedRoute><RecommendationResults /></ProtectedRoute>} />
            <Route path="/verify-tasks" element={<PrivilegedRoute><VerifyTasks /></PrivilegedRoute>} />
            <Route path="/feedback" element={<PrivilegedRoute><FeedbackForm /></PrivilegedRoute>} />
            <Route path="/ai-extraction-review" element={<PrivilegedRoute><AIExtractionReview /></PrivilegedRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
