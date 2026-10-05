import { lazy, Suspense } from 'react'
import { Skeleton } from 'antd'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import ProjectsPage from './pages/ProjectsPage'
import SchemesPage from './pages/SchemesPage'
import { isMock } from './constants/dimensions'
import MockControls from './components/MockControls'
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))

export default function App() {
  const location = useLocation()
  const projectId = location.pathname.match(/projects\/(\d+)/)?.[1]
  return <div className="app-shell">
    <aside className="app-rail">
      <NavLink to="/projects" className="brand"><span className="brand-mark" aria-hidden="true">衡</span><span>筑衡<small>建筑方案智能比选</small></span></NavLink>
      <div className="rail-label">工作空间</div>
      <nav aria-label="主导航">
        <NavLink end to="/projects"><span aria-hidden="true">▦</span>项目总览</NavLink>
        {projectId && <>
          <NavLink to={'/projects/' + projectId + '/schemes'}><span>01</span>方案录入</NavLink>
          <NavLink to={'/projects/' + projectId + '/dashboard'}><span>02</span>对比看板</NavLink>
          <NavLink to={'/projects/' + projectId + '/chat'}><span>03</span>对话与报告</NavLink>
        </>}
      </nav>
      <div className="rail-bottom"><span className="status-dot" />{isMock ? '离线演示' : '后端服务'}<p>每一项比较，都有依据。</p></div>
    </aside>
    <div className="app-body">
      <header className="topbar"><span>方案决策工作台</span><span className="muted">{isMock ? '【示例】虚构数据 · 仅供开发调试' : '评分与排序由后端计算'}</span></header>
      <main className="workspace"><Suspense fallback={<Skeleton active paragraph={{rows:8}} />}><Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:id/schemes" element={<SchemesPage />} />
        <Route path="/projects/:id/dashboard" element={<DashboardPage />} />
        <Route path="/projects/:id/chat" element={<ChatPage />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes></Suspense></main>
      {isMock && <div className="mock-tools"><MockControls /></div>}
      <footer className="app-footer">筑衡 · 从方案参数到可解释的取舍<span>品质 / 结构 / 施工 / 绿色</span></footer>
    </div>
  </div>
}
