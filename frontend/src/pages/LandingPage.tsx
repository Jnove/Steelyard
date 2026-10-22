import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowRight, BookOpen, Scale } from 'lucide-react'
import { projects } from '../api/projects'
import { schemes } from '../api/schemes'
import BuildingShowcase from '../components/BuildingShowcase'
import { Button } from '../components/ui/button'
import { featuredProject, isTeachingCase } from '../utils/project-presentation'
import '../landing.css'
import { IconScale, IconShieldCheck, IconMessage } from '../components/Icons'

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
        <div className="landing-header-inner">
          <Link className="landing-brand" to="/" aria-label="筑衡 · 首页">
            <span className="landing-brand-mark"><Scale size={25} strokeWidth={1.6} aria-hidden="true" /></span>
            <span className="landing-brand-name">筑衡</span><span className="landing-brand-english">Steelyard</span>
          </Link>
          <nav aria-label="首页导航">
            <Button asChild variant="ghost" className="landing-nav-help"><a href="#workflow"><BookOpen size={17} aria-hidden="true" />如何使用</a></Button>
            <Button asChild variant="outline" className="landing-nav-workspace"><Link to="/projects">项目工作台 <ArrowRight size={18} aria-hidden="true" /></Link></Button>
          </nav>
        </div>
      </header>
      <main id="landing-main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-copy">
            <p className="landing-eyebrow"><span>STEELYARD</span><span aria-hidden="true">·</span>建筑方案比选智能体</p>
            <h1 id="landing-title" aria-label="好房子，有据可选。">
              <span className="landing-title-line">好房子<span className="landing-title-mark">，</span></span>
              <span className="landing-title-line">有据可选<span className="landing-title-mark landing-title-mark-stop">。</span></span>
            </h1>
            <div className="landing-copy-deck">
              <p className="landing-intro"><span>建筑方案</span><span>智能比选</span></p>
              <p className="landing-description"><span>比较品质、结构、施工与绿色。</span><span>沿评分依据追问，再讨论调整。</span></p>
            </div>
            <div className="landing-actions">
              <Button asChild><Link to="/projects">进入项目工作台 <ArrowRight size={19} aria-hidden="true" /></Link></Button>
              <a className="landing-process-link" href="#workflow">了解比选流程 <ArrowDown size={17} aria-hidden="true" /></a>
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

        <section className="workflow-strip landing-workflow-strip" aria-label="比选工作流程" id="workflow" aria-labelledby="workflow-title">
          <section><div className="landing-workflow-heading"><h2 id="workflow-title" style={{fontSize:24}}>从方案，到有依据的选择。</h2><Link to="/projects">开始一次比选 <ArrowRight size={17} /></Link></div></section>

          <section className="landing-workflow-steps">
            <div><span className="workflow-number"  style={{fontSize:14}}>01</span><IconScale size={20} /><h2 style={{fontSize:20}}>录入地块与方案</h2><p style={{fontSize:16}}>建立项目，手动填写或导入 Excel。不确定的参数可以留空。</p></div>
            <div><span className="workflow-number" style={{fontSize:14}}>02</span><IconShieldCheck size={20}/><h3 style={{fontSize:20}}>比较表现与取舍</h3><p style={{fontSize:16}}>切换角色与权重，查看方案差异，追溯参数、公式与规则来源。</p></div>
            <div><span className="workflow-number"  style={{fontSize:14}}>03</span><IconMessage size={20} /><h3 style={{fontSize:20}}>追问、推演与报告</h3><p style={{fontSize:16}}>围绕当前方案解释结果；参数调整先预览，确认后再生成副本。</p></div>
          </section>

        </section>
      </main>
      <footer className="landing-footer"><span>筑衡 · 建筑方案决策工作台</span><span>当前规则与专业依据仍需核定</span><Link to="/projects">进入工作台 <ArrowRight size={15} /></Link></footer>
    </div>
  )
}
