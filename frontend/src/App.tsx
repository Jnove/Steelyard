import { lazy, Suspense } from 'react'
import { Skeleton } from 'antd'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import HomeShell from './components/home/HomeShell'
import { loadDashboardPage, loadSchemesPage } from './routes/page-loaders'

const LandingPage = lazy(() => import('./pages/LandingPage'))
const ProjectsPage = lazy(() => import('./pages/ProjectsPage'))
const SchemesPage = lazy(loadSchemesPage)
const DashboardPage = lazy(loadDashboardPage)
const ChatPage = lazy(() => import('./pages/ChatPage'))

export default function App() {
  return (
    <Suspense fallback={<div className="route-loading"><Skeleton active paragraph={{ rows: 8 }} /></div>}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<HomeShell><Suspense fallback={<div className="route-loading"><Skeleton active paragraph={{ rows: 8 }} /></div>}><Outlet /></Suspense></HomeShell>}>
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id/schemes" element={<SchemesPage />} />
          <Route path="/projects/:id/dashboard" element={<DashboardPage />} />
          <Route path="/projects/:id/chat" element={<ChatPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
