import { lazy, Suspense } from 'react'
import { Skeleton } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { projects } from './api/projects'
import ProjectsPage from './pages/ProjectsPage'
import SchemesPage from './pages/SchemesPage'
import { isMock } from './constants/dimensions'
import MockControls from './components/MockControls'
import { IconLayers, IconMessage, IconScale, IconSliders } from './components/Icons'
import HomeShell from './components/home/HomeShell'
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))

export default function App() {
  const location = useLocation()
  const projectId = location.pathname.match(/projects\/(\d+)/)?.[1]
  const showProjectName = !!projectId && /\/(dashboard|chat)\/?$/.test(location.pathname)
  const id = Number(projectId)
  const project = useQuery({ queryKey: ['project', id], queryFn: () => projects.get(id), enabled: showProjectName })
  const projectName = project.data?.name ?? (project.isError ? '项目名称暂不可用' : '正在加载项目…')
  if (!projectId) return <HomeShell><Routes>
    <Route path="/projects" element={<ProjectsPage />} />
    <Route path="*" element={<Navigate to="/projects" replace />} />
  </Routes></HomeShell>
  return <div className={'app-shell ' + (projectId ? 'app-shell-project' : 'app-shell-overview')}>
    <header className={'app-rail glass-surface' + (showProjectName ? ' app-rail-with-project' : '')}>
      <div className="rail-identity">
        <NavLink to="/projects" className="brand" aria-label="筑衡 · 返回项目总览"><span className="brand-mark" aria-hidden="true"><IconScale size={23} /></span><span>筑衡<small>STEELYARD</small></span></NavLink>
        {showProjectName && <span className="rail-project-name" aria-label={'当前项目：' + projectName} title={projectName}>{projectName}</span>}
      </div>
      <nav aria-label="主导航">
        <NavLink end to="/projects"><IconLayers size={16} />项目总览</NavLink>
        {projectId && <>
          <NavLink to={'/projects/' + projectId + '/schemes'}><IconLayers size={16} />方案录入</NavLink>
          <NavLink to={'/projects/' + projectId + '/dashboard'}><IconSliders size={16} />对比看板</NavLink>
          <NavLink to={'/projects/' + projectId + '/chat'}><IconMessage size={16} />对话与报告</NavLink>
        </>}
      </nav>
      <span className="rail-status"><span className="status-dot" />{isMock ? '离线演示' : '方案决策工作台'}</span>
    </header>
    <div className="app-body">
      <div className="topbar"><span>{projectId ? '工作空间 / 方案比选' : '建筑方案智能比选'}</span><span className="muted">{isMock ? '【示例】虚构数据 · 仅供开发调试' : '评分与排序由后端计算'}</span></div>
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
