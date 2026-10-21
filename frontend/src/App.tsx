import { lazy, Suspense } from 'react'
import { Skeleton } from 'antd'
import { Navigate, Route, Routes } from 'react-router-dom'
import ProjectsPage from './pages/ProjectsPage'
import SchemesPage from './pages/SchemesPage'
import HomeShell from './components/home/HomeShell'

const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))

export default function App() {
  return (
    <HomeShell>
      <Suspense fallback={<Skeleton active paragraph={{ rows: 8 }} />}>
        <Routes>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id/schemes" element={<SchemesPage />} />
          <Route path="/projects/:id/dashboard" element={<DashboardPage />} />
          <Route path="/projects/:id/chat" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </Suspense>
    </HomeShell>
  )
}
