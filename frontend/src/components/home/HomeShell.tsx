import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  FolderClosed,
  FolderOpen,
  Layers3,
  Leaf,
  PanelLeftClose,
  Scale,
  ShieldCheck,
  HardHat,
  House,
  Menu,
  SlidersHorizontal,
  MessageSquare,
} from 'lucide-react'
import { projects } from '../../api/projects'
import { USE_MOCK } from '../../api/client'
import { projectOptions } from '../../utils/project-queries'
import { usePagePrefetch } from '../../utils/use-page-prefetch'
import { projectNameParts } from '../../utils/presentation-names'
import { Button } from '../ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../ui/dialog'

export default function HomeShell({ children }: { children: ReactNode }) {
  const [help, setHelp] = useState(false)
  const helpTrigger = useRef<HTMLButtonElement>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const menuTrigger = useRef<HTMLButtonElement>(null)
  const location = useLocation()
  const navigate = useNavigate()
  const prefetch = usePagePrefetch()
  const projectId = Number(location.pathname.match(/\/projects\/(\d+)/)?.[1])
  const section = location.pathname.split('/').at(-1)
  const pageName = section === 'schemes' ? '方案录入' : section === 'dashboard' ? '对比看板' : section === 'chat' ? '对话与报告' : '项目总览'
  const query = useQuery({
    queryKey: ['projects'],
    queryFn: () => projects.list(),
  })
  const recent = [...(query.data ?? [])]
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
    .slice(0, 5)
  const current = useQuery({ ...projectOptions(projectId), enabled: Number.isSafeInteger(projectId) && projectId > 0 })
  const destinations = [
    { to: '/projects', label: '项目总览', icon: FolderOpen },
    ...(projectId > 0 ? [
      { to: `/projects/${projectId}/schemes`, label: '方案录入', icon: Layers3 },
      { to: `/projects/${projectId}/dashboard`, label: '对比看板', icon: SlidersHorizontal },
      { to: `/projects/${projectId}/chat`, label: '对话与报告', icon: MessageSquare },
    ] : []),
  ]
  const navigation = (close?: () => void) => destinations.map(item => <NavLink end key={item.to} to={item.to} {...prefetch(item.to)} onClick={close} className={({ isActive }) => isActive ? 'home-nav-active' : ''}><item.icon size={17} /><span>{item.label}</span></NavLink>)
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])
  useEffect(() => {
    const previous = document.title
    document.title = `${pageName} · 筑衡`
    document.body.classList.add('home-active')
    return () => {
      document.body.classList.remove('home-active')
      document.title = previous
    }
  }, [pageName])
  return (
    <div
      className={`home-theme home-shell${projectId > 0 ? ' workbench-shell' : ''}${collapsed ? ' home-shell-collapsed' : ''}`}
    >
      <a href="#home-main" className="home-skip">
        跳到主要内容
      </a>
      <aside className="home-sidebar" aria-label="工作空间导航">
        <Link
          to="/"
          className="home-brand"
          aria-label="筑衡 · 返回首页"
        >
          <span className="home-brand-mark">
            <Scale size={23} strokeWidth={1.7} />
          </span>
          <span>
            筑衡<small>STEELYARD</small>
          </span>
        </Link>
        <Button ref={menuTrigger} className="workbench-mobile-menu" variant="ghost" size="icon" aria-label="打开页面导航" onClick={() => setMobileOpen(true)}><Menu size={20} /></Button>
        {projectId > 0 && <div className="workbench-project-switch"><label htmlFor="workspace-project">当前项目</label><select id="workspace-project" aria-label="切换当前项目" title={current.data?.name} value={projectId} onChange={event => navigate(`/projects/${event.target.value}/${section}`)}>
          {!(query.data ?? []).some(project => project.id === projectId) && <option value={projectId}>{current.data ? projectNameParts(current.data.name).title : '正在加载项目…'}</option>}
          {query.data?.map(project => <option key={project.id} value={project.id} title={project.name}>{projectNameParts(project.name).title}</option>)}
        </select></div>}
        <div className="home-sidebar-section">
          <span>工作空间</span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed(true)}
            aria-label="收起侧栏"
          >
            <PanelLeftClose size={15} />
          </Button>
        </div>
        <nav aria-label="主导航">
          {navigation()}
        </nav>
        {recent.length > 0 && (
          <>
            <p className="home-sidebar-section home-recent-label">最近项目</p>
            <nav className="home-recent" aria-label="最近项目">
              {recent.map((project) => (
                <Link
                  key={project.id}
                  to={`/projects/${project.id}/schemes`}
                  {...prefetch(`/projects/${project.id}/schemes`)}
                  title={project.name}
                >
                  <FolderClosed size={15} />
                  <span>{projectNameParts(project.name).title}</span>
                </Link>
              ))}
            </nav>
          </>
        )}
        <div className="home-sidebar-bottom">
          <Button
            variant="ghost"
            className="home-help-button"
            ref={helpTrigger}
            onClick={() => setHelp(true)}
          >
            <BookOpen size={16} />
            使用指南
            <ArrowUpRight size={13} />
          </Button>
          <div className="home-sidebar-note">
            <Layers3 size={17} />
            <span>
              让方案取舍有据可循<small>参数 · 比较 · 追溯</small>
            </span>
          </div>
        </div>
      </aside>
      <div className="home-body">
        <header className="home-topbar">
          <div className="workbench-topbar-start">
            {collapsed && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCollapsed(false)}
                aria-label="展开侧栏"
              >
                <PanelLeftClose size={17} />
              </Button>
            )}
            <nav className="workbench-breadcrumb" aria-label="页面路径"><ol>
              <li><Link className="home-breadcrumb-parent" to="/projects">工作空间</Link></li>
              <li className="workbench-path-divider" aria-hidden="true"><ChevronRight size={13} /></li>
              {projectId > 0 && <>
                <li className="workbench-path-project"><Link className="workbench-breadcrumb-project" to={`/projects/${projectId}/schemes`} {...prefetch(`/projects/${projectId}/schemes`)} title={current.data?.name}>{current.data ? projectNameParts(current.data.name).title : '正在加载项目…'}</Link></li>
                <li className="workbench-path-divider" aria-hidden="true"><ChevronRight size={13} /></li>
              </>}
              <li><span aria-current="page">{pageName}</span></li>
            </ol></nav>
          </div>
          <span className="home-mode">
            {USE_MOCK ? '离线预览 · 示例数据' : '建筑方案智能比选'}
          </span>
        </header>
        <main id="home-main" className={`home-main${projectId > 0 ? ' workbench-main' : ''}`} tabIndex={-1}>
          {children}
        </main>
        <footer className="home-footer">
          <span>筑衡 · 建筑方案决策工作台</span>
          <div>
            <span>
              <House size={13} />
              品质
            </span>
            <span>
              <ShieldCheck size={13} />
              结构
            </span>
            <span>
              <HardHat size={13} />
              施工
            </span>
            <span>
              <Leaf size={13} />
              绿色
            </span>
          </div>
        </footer>
      </div>
      <Dialog open={help} onOpenChange={setHelp}>
        <DialogContent
          className="home-help-dialog"
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            helpTrigger.current?.focus()
          }}
        >
          <DialogTitle>开始一次方案比选</DialogTitle>
          <DialogDescription>
            从地块条件到比较依据，所有操作围绕同一个项目展开。
          </DialogDescription>
          <ol className="home-guide">
            <li>
              <strong>建立项目</strong>
              <p>录入已知地块条件；不确定的参数可以留空。</p>
            </li>
            <li>
              <strong>添加候选方案</strong>
              <p>手动录入或在方案页导入 Excel，使用同一组指标比较。</p>
            </li>
            <li>
              <strong>查看差异与依据</strong>
              <p>运行评估，调整角色与权重，并查看分数对应的输入和规则。</p>
            </li>
            <li>
              <strong>追问与推演</strong>
              <p>进入对话与报告；参数调整先预览，确认后生成方案副本。</p>
            </li>
          </ol>
          <p className="home-boundary">
            教学方案和虚构示例用于讨论流程；专业规则与来源仍需核定。
          </p>
        </DialogContent>
      </Dialog>
      <Dialog open={mobileOpen} onOpenChange={setMobileOpen}><DialogContent className="workbench-mobile-navigation" onCloseAutoFocus={event => { event.preventDefault(); menuTrigger.current?.focus() }}><DialogTitle>筑衡 · 页面导航</DialogTitle><DialogDescription>{current.data?.name ?? '建筑方案智能比选工作台'}</DialogDescription><nav aria-label="页面导航">{navigation(() => setMobileOpen(false))}</nav><Button variant="outline" onClick={() => { setMobileOpen(false); setHelp(true) }}>使用指南</Button></DialogContent></Dialog>
    </div>
  )
}
