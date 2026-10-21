import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowRight, Scale } from 'lucide-react'
import { projects } from '../api/projects'
import { schemes } from '../api/schemes'
import BuildingShowcase from '../components/BuildingShowcase'
import { Button } from '../components/ui/button'
import { featuredProject, isTeachingCase } from '../utils/project-presentation'
import '../landing.css'

export default function LandingPage() {
  const [selectedId, setSelectedId] = useState<number>()
  const projectQuery = useQuery({ queryKey: ['projects'], queryFn: () => projects.list() })
  const project = featuredProject(projectQuery.data, selectedId)
  const schemeQuery = useQuery({
    queryKey: ['schemes', project?.id],
    queryFn: () => schemes.list(project!.id),
    enabled: !!project,
  })
  const caseLabel = project ? isTeachingCase(project) ? '真实地块参考 · 教学方案'
    : project.name.includes('虚构') ? '虚构案例 · 流程演示' : '当前展示项目' : '建筑方案展示'
  useEffect(() => {
    const previous = document.title
    document.title = '筑衡 · 建筑方案智能比选'
    document.body.classList.add('landing-active')
    window.scrollTo(0, 0)
    return () => {
      document.body.classList.remove('landing-active')
      document.title = previous
    }
  }, [])
  return (
    <div className="landing-page">
      <a className="landing-skip" href="#landing-main">跳到主要内容</a>
      <header className="landing-header">
        <Link className="landing-brand" to="/" aria-label="筑衡 · 首页">
          <span className="landing-brand-mark"><Scale size={27} strokeWidth={1.7} /></span>
          <span>筑衡<small>Steelyard</small></span>
        </Link>
        <nav aria-label="首页导航">
          <a href="#workflow">如何使用</a>
          <Link to="/projects">项目工作台 <ArrowRight size={17} /></Link>
        </nav>
      </header>
      <main id="landing-main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-copy">
            <h1 id="landing-title">好房子，<br />有据可选。</h1>
            <p className="landing-intro">建筑方案智能比选，让品质、结构、施工与绿色之间的取舍看得见、说得清。</p>
            <p className="landing-description">从候选方案出发，比较参数与四维表现，沿评分依据追问，再讨论调整的可能。</p>
            <div className="landing-actions">
              <Button asChild><Link to="/projects">进入项目工作台 <ArrowRight size={19} /></Link></Button>
              <a className="landing-process-link" href="#workflow">了解比选流程 <ArrowDown size={17} /></a>
            </div>
            <div className="landing-case">
              <label htmlFor="landing-project">{caseLabel}</label>
              {project ? <>
                <select id="landing-project" aria-label="选择展台项目" value={project.id}
                  onChange={event => setSelectedId(Number(event.target.value))}>
                  {projectQuery.data?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <p>展台按已录入参数绘制，仅作体量示意。{isTeachingCase(project) ? '候选方案为教学推演，不代表实际建成方案。' : project.name.includes('虚构') ? '案例用于演示比选流程，专业依据仍需核定。' : '不包含真实空间布局。'}</p>
              </> : <p>{projectQuery.isPending ? '正在载入展示项目…' : projectQuery.isError ? '展示项目暂未载入，仍可进入工作台。' : '还没有展示项目，进入工作台录入第一组候选方案。'}</p>}
              {projectQuery.isError && <div role="alert"><p>{projectQuery.error.message}</p><button type="button" onClick={() => void projectQuery.refetch()}>重新加载展示项目</button></div>}
            </div>
          </div>
          <div className="landing-showcase-ui" data-ui>
            <BuildingShowcase key={project?.id ?? 'empty'} schemes={schemeQuery.data ?? []}
              pending={projectQuery.isPending || (!!project && schemeQuery.isPending)}
              failed={projectQuery.isError || schemeQuery.isError}
              onRetry={() => { if (projectQuery.isError) void projectQuery.refetch(); else void schemeQuery.refetch() }} />
          </div>
        </section>
        <section className="landing-workflow" id="workflow" aria-labelledby="workflow-title">
          <div className="landing-workflow-heading"><h2 id="workflow-title">从方案，到有依据的选择。</h2><Link to="/projects">开始一次比选 <ArrowRight size={17} /></Link></div>
          <ol>
            <li><h3>录入地块与方案</h3><p>建立项目，手动填写或导入 Excel。不确定的参数可以留空。</p></li>
            <li><h3>比较表现与取舍</h3><p>切换角色与权重，查看方案差异，追溯参数、公式与规则来源。</p></li>
            <li><h3>追问、推演与报告</h3><p>围绕当前方案解释结果；参数调整先预览，确认后再生成副本。</p></li>
          </ol>
        </section>
      </main>
      <footer className="landing-footer"><span>筑衡 · 建筑方案决策工作台</span><span>当前规则与专业依据仍需核定</span><Link to="/projects">进入工作台 <ArrowRight size={15} /></Link></footer>
    </div>
  )
}
