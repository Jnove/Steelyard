import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Radio, Select, Skeleton, Slider, Tag, Tooltip } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ranking } from '../api/ranking'
import { evaluationOptions, projectOptions, roleQueryOptions } from '../utils/project-queries'
import type { EvalResult, RankResponse } from '../api/types'
import { dimensions, type DimensionKey, isMock } from '../constants/dimensions'
import { schemeColor, tokens } from '../theme'
import { redistributeWeights } from '../utils/weights'
import { decisionInput, decisionLabel } from '../utils/decision-context'
import { useDecisionContext } from '../utils/use-decision-context'
import { evaluationSummary, scoreTradeoff } from '../utils/scheme-presentation'
import { projectNameParts, schemeNameParts, shortSchemeLabel } from '../utils/presentation-names'
import Chart from '../components/Chart'
import RankProbability from '../components/RankProbability'
import TraceDrawer from '../components/TraceDrawer'
import ComparisonWorkbench from '../components/comparison/ComparisonWorkbench'
import {
  IconAlertTriangle,
  IconArrowRight,
  IconAward,
  IconBan,
  IconCheck,
  IconHelpCircle,
  IconMessage,
} from '../components/Icons'

type RankInput = ReturnType<typeof decisionInput>

function SchemeRadar({ results, leadingId }: { results: EvalResult[]; leadingId?: string }) {
  const container = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(460)
  useEffect(() => {
    if (!container.current) return
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width))
    observer.observe(container.current)
    return () => observer.disconnect()
  }, [])
  const compact = width < 350
  return <div ref={container}><Chart height={compact && results.length > 3 ? 400 : 370} label="各方案四维得分雷达图" option={{
    tooltip: { textStyle: { fontSize: tokens.fontSize } },
    legend: { bottom: 12, left: 8, right: 8, type: results.length > 5 ? 'scroll' : 'plain', itemGap: 16, formatter: (name: string) => shortSchemeLabel(name), tooltip: { show: true }, textStyle: { fontSize: tokens.small } },
    radar: {
      center: ['50%', compact && results.length > 3 ? '32%' : '40%'], radius: compact ? '50%' : '55%',
      indicator: dimensions.map(d => ({ name: d.label, max: 100 })),
      axisName: { color: tokens.ink, fontSize: tokens.small, formatter: (name = '') => compact ? name.slice(0, 2) + '\n' + name.slice(2) : name },
      splitArea: { show: false }, splitLine: { lineStyle: { color: tokens.border } },
    },
    series: [{ type: 'radar', data: results.map(e => ({
      name: e.scheme_name || e.scheme_id, value: dimensions.map(d => e.dimension_scores?.[d.key] ?? 0),
      lineStyle: { type: (e.compliance ?? []).some(c => c.status === 'failed' && c.severity === 'error') ? 'dashed' : 'solid', width: e.scheme_id === leadingId ? 3 : 1.8 },
      itemStyle: { color: schemeColor(e.scheme_id) }, areaStyle: { opacity: e.scheme_id === leadingId ? .12 : .025 }, symbolSize: e.scheme_id === leadingId ? 6 : 4,
    })) }],
  }} /></div>
}

function RankingList({ result }: { result: RankResponse }) {
  const container = useRef<HTMLDivElement>(null)
  const positions = useRef(new Map<string, number>())
  useLayoutEffect(() => {
    const next = new Map<string, number>()
    container.current?.querySelectorAll<HTMLElement>('[data-scheme]').forEach(el => {
      const id = el.dataset.scheme!
      const top = el.getBoundingClientRect().top
      next.set(id, top)
      const previous = positions.current.get(id)
      if (previous != null && previous !== top && !matchMedia('(prefers-reduced-motion: reduce)').matches)
        el.animate([{ transform: 'translateY(' + (previous - top) + 'px)' }, { transform: 'translateY(0)' }],
          { duration: tokens.duration, easing: 'cubic-bezier(.2,.7,.2,1)' })
    })
    positions.current = next
  }, [result])
  return <div ref={container} className="ranking-list" aria-label="方案排名">
    {result.ranking.map(s => {
      return (
        <div className={'ranking-row ' + (s.rank === 1 ? 'ranking-first' : '')} key={s.scheme_id} data-scheme={s.scheme_id}>
          <span className="rank-number">{String(s.rank).padStart(2, '0')}</span>
          <div className="rank-detail">
            <div className="rank-line">
              <span>
                <strong title={s.scheme_name}>{schemeNameParts(s.scheme_name).title}</strong>
              </span>
              <span className="numeric">{s.closeness.toFixed(3)}</span>
            </div>
          <div className="rank-track"><div style={{ width: s.closeness * 100 + '%', background: schemeColor(s.scheme_id) }} /></div>
          </div>
        </div>
      )
    })}
    {result.excluded.map(s => <div key={s.scheme_id} className="excluded-row">
      <div className="excluded-header">
        <IconBan size={15} style={{ color: 'var(--color-danger)' }} />
        <strong title={s.scheme_name}>{schemeNameParts(s.scheme_name).title} · 未参与排名</strong>
      </div>
      <p>{s.failed_rules.length ? '硬约束未通过：'+s.failed_rules.join('、') : s.reason}</p>
    </div>)}
  </div>
}

export default function DashboardPage() {
  const { id: rawId } = useParams()
  const id = Number(rawId)
  if (!Number.isSafeInteger(id) || id <= 0) return <Alert type="error" message="项目 ID 无效" />
  return <ProjectDashboard key={id} id={id} />
}

function ProjectDashboard({ id }: { id: number }) {
  const [context, updateContext] = useDecisionContext(id)
  const role = context.role
  const [weights, setWeights] = useState(context.weights ?? [.25,.25,.25,.25])
  const request = decisionInput(context)
  const [debounced, setDebounced] = useState<RankInput>(request)
  const [trace, setTrace] = useState<{ evaluation: EvalResult; dimension?: DimensionKey; ruleId?: string }>()
  const project = useQuery(projectOptions(id))
  const evaluated = useQuery(evaluationOptions(id))
  const roles = useQuery(roleQueryOptions(id))
  const requestKey = JSON.stringify(request)
  useEffect(() => { const timer = setTimeout(() => setDebounced(JSON.parse(requestKey) as RankInput), 150); return () => clearTimeout(timer) }, [requestKey])
  useEffect(() => {
    const preset = roles.data?.roles.find(r => r.role === role)
    if (preset) setWeights(preset.weights)
  }, [roles.data,role])
  const ranked = useQuery({
    queryKey: ['rank',id,debounced], queryFn: () => ranking.run(id,debounced),
    enabled: !!evaluated.data?.results.length,
    placeholderData: (previous,query) => query?.queryKey[1] === id ? previous : undefined,
  })
  const results = evaluated.data?.results ?? []
  const result = ranked.data
  const rankingPending = ranked.isFetching || requestKey !== JSON.stringify(debounced)
  const preset = roles.data?.roles.find(template => template.role === role)
  const currentWeightsUsed = result?.weights_used.role === role
    ? result?.weights_used : undefined
  const templateWeights = preset ?? currentWeightsUsed
  const sensitivity = result?.sensitivity
  const acceptability = result?.rank_acceptability
  const roleChange = (value: string | number) => {
    const key = String(value)
    if (key === role) return
    const startingWeights = preset?.weights ?? weights
    if (key === 'custom') setWeights(startingWeights)
    updateContext({ role: key, weights: key === 'custom' ? startingWeights : undefined })
  }
  const changeWeight = (index: number, value: number) => {
    if (role !== 'custom') return
    const next = redistributeWeights(weights,index,value / 100)
    setWeights(next); updateContext({ role: 'custom', weights: next })
  }
  const inputOrder = result?.scheme_order ?? []
  const nameAt = (index: number | null) => index == null ? '—' :
    results.find(e => e.scheme_id === inputOrder[index])?.scheme_name ?? '—'
  const error = evaluated.error ?? roles.error ?? ranked.error
  const ahp = templateWeights?.ahp

  // 动态提炼推荐结论
  const topScheme = result?.ranking?.[0]
  const selectedSchemeId = results.find(item => item.scheme_id === context.schemeId)?.scheme_id ?? topScheme?.scheme_id ?? results[0]?.scheme_id
  const topEval = results.find(e => e.scheme_id === topScheme?.scheme_id)
  const excludedCount = result?.excluded?.length ?? 0
  const topSummary = topEval ? evaluationSummary(topEval) : undefined
  const participating = results.filter(e => result?.ranking.some(r => r.scheme_id === e.scheme_id))

  const roleOptions = (roles.data?.roles ?? []).map(template => ({
    label: template.role_name ?? template.role ?? '角色模板', value: template.role ?? '',
  }))
  const roleNameMap: Record<string, string> = {
    ...Object.fromEntries(roleOptions.map(option => [option.value, option.label])), custom: '自定义权重',
  }

  return <>
    <div className="page-heading">
      <div>
        <p className="eyebrow">筑衡 · 多维量化比选</p>
        <h1>方案对比看板</h1>
        <p className="page-description" title={project.data?.name}>{project.data ? projectNameParts(project.data.name).title : '正在加载项目'} · 比较四维得分与方案差异，沿计算依据核对取舍</p>
        {project.data && projectNameParts(project.data.name).detail && <p className="project-name-detail">{projectNameParts(project.data.name).detail}</p>}
      </div>
      <div className="action-row">
        <Link to={'/projects/'+id+'/schemes'}><Button>编辑方案</Button></Link>
        <Link to={'/projects/'+id+'/chat'} onClick={() => updateContext({ schemeId: selectedSchemeId })}><Button type="primary">讨论与报告 <IconArrowRight size={15} style={{ verticalAlign: 'middle', marginLeft: 4 }} /></Button></Link>
      </div>
    </div>

    {error && <Alert showIcon type="error" message="评估或排序数据未就绪" description={error.message}
      action={<Button onClick={() => { void evaluated.refetch(); void roles.refetch(); void ranked.refetch() }}>重试</Button>} />}
    {evaluated.isLoading && <Skeleton active paragraph={{ rows: 9 }} />}
    {evaluated.isSuccess && !results.length && <div className="panel"><Empty description="还没有评估结果，请先录入方案并开始评估"><Link to={'/projects/'+id+'/schemes'}><Button type="primary">去录入方案</Button></Link></Empty></div>}

    {!!results.length && <>
      {/* 决策视角切换栏 */}
      <section className="role-bar" aria-label="决策视角">
        <div className="role-bar-controls">
          <h2>决策视角</h2>
          <Radio.Group className="decision-role-options" aria-label="选择决策视角" value={role}
            onChange={event => roleChange(event.target.value)} optionType="button"
            options={[...roleOptions, { label: '自定义', value: 'custom' }]} />
          <span className="role-state" aria-live="polite">{rankingPending ? '正在更新排名…' : role === 'custom' ? '自定义权重 · 可调整' : '模板权重 · 只读'}</span>
        </div>
        {role !== 'custom' && <>
          <div className="role-weight-meta">
            <dl className="role-weight-summary" aria-label="当前视角权重">{dimensions.map((dimension, index) => <div key={dimension.key}>
              <dt>{dimension.label}</dt><dd>{templateWeights ? `${(templateWeights.weights[index] * 100).toFixed(1)}%` : '—'}</dd>
            </div>)}</dl>
            <details className="role-weight-details"><summary>权重说明</summary>
              <p className="role-weight-note">{templateWeights ? ahp ? `一致性 CR ${ahp.cr.toFixed(4)} · ${ahp.consistent ? '一致性检验通过（判断自洽）' : '模板需复核'}。` : '直接赋权，无两两比较矩阵。' : '等待当前视角权重。'}选择“自定义”可调整权重。</p>
              {templateWeights?.note && <p className="role-weight-note">{templateWeights.note}</p>}
            </details>
          </div>
          {templateWeights?.consistency_warning && <Alert type="warning" message={templateWeights.consistency_warning} />}
        </>}
      </section>
      {role === 'custom' && <section className="panel weights-panel custom-weights-panel" aria-label="自定义评价权重">
        <div className="section-heading"><div><h2>调整评价权重</h2><p className="section-subtext">拖动一个维度，其余按比例调整，结果随之更新。</p></div><span className="custom-weight-total">权重合计 100%</span></div>
        <div className="custom-weights-grid">{dimensions.map((dimension, index) => <div className="weight-control" key={dimension.key}>
          <div className="weight-label"><span><i style={{ background: dimension.color }} />{dimension.label}</span><strong className="numeric">{(weights[index] * 100).toFixed(1)}<small>%</small></strong></div>
          <Slider min={0} max={100} step={1} value={weights[index] * 100} onChange={value => changeWeight(index, value)}
            ariaLabelForHandle={dimension.label + '权重'} tooltip={{ formatter: value => value?.toFixed(1) + '%' }} />
        </div>)}</div>
        <p className="custom-weight-note">自定义采用直接赋权，不计算两两比较矩阵的一致性 CR。</p>
      </section>}
      <div className="action-row" style={{ marginBottom: 16 }} aria-label="当前讨论上下文">
        <Tag>{decisionLabel(context)}</Tag>
        <Select aria-label="选择讨论方案" value={selectedSchemeId} style={{ minWidth: 220 }}
          options={results.map(item => ({ value: item.scheme_id, label: schemeNameParts(item.scheme_name ?? item.scheme_id).title, title: item.scheme_name }))}
          onChange={schemeId => updateContext({ schemeId })} />
        <span className="muted">讨论与报告沿用当前视角、权重和所选方案。</span>
      </div>

      {!!project.data?.params.scoring_exclusions?.length && (
        <Alert showIcon type="info" style={{ marginBottom: 16 }}
          message={'暂不纳入评分：' + project.data.params.scoring_exclusions.join('、')}
          description="这些代理指标的适用性尚未确认，不参与维度均值，也不能作为方案性能优势。原因见案例来源与边界。" />
      )}
      {project.data?.params.project_notes && <details className="panel" style={{ marginBottom: 16 }}>
        <summary>案例来源与评分边界</summary>
        <p style={{ whiteSpace: 'pre-wrap' }}>{project.data.params.project_notes}</p>
      </details>}

      {/* 核心决策简报 (Executive Recommendation Card) */}
      {result && topScheme && (
        <section className="panel executive-summary-card" aria-label="决策建议简报" aria-busy={rankingPending}>
          <div className="executive-card-header">
            <div className="executive-lead-title">
              <div className="executive-badge">
                <IconAward size={16} />
                <span>已知条件与当前权重下的优先方案</span>
              </div>
              <h2 title={topScheme.scheme_name}>{schemeNameParts(topScheme.scheme_name).title}</h2>
              {schemeNameParts(topScheme.scheme_name).detail && <small className="name-detail">{schemeNameParts(topScheme.scheme_name).detail}</small>}
              <div className="executive-submeta">
                <Tag color="blue">结果视角：{roleNameMap[result.weights_used.role ?? 'custom'] ?? result.weights_used.role_name ?? result.weights_used.role}</Tag>
                <Tag color="green">综合排名第 {topScheme.rank} 名</Tag>
                <span className="executive-metric">TOPSIS 贴近度：<strong>{topScheme.closeness.toFixed(4)}</strong></span>
              </div>
            </div>
            <div className="executive-actions">
              <Link to={`/projects/${id}/chat`} onClick={() => updateContext({ schemeId: topScheme.scheme_id })}>
                <Button type="primary" size="large">
                  <IconMessage size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                  追问推荐依据
                </Button>
              </Link>
            </div>
          </div>

          <div className="executive-points-grid">
            <div className="executive-point positive">
              <div className="point-icon"><IconCheck size={16} /></div>
              <div>
                <strong>当前得分表现</strong>
                <p>
                  {topSummary?.desc ?? '在当前候选集合与权重下，综合贴近度排名靠前。请结合参数与规则依据复核。'}
                </p>
              </div>
            </div>

            <div className="executive-point trade-off">
              <div className="point-icon"><IconAlertTriangle size={16} /></div>
              <div>
                <strong>需要接受的取舍</strong>
                <p>
                  {scoreTradeoff(topEval, participating)}
                </p>
              </div>
            </div>

            {excludedCount > 0 && (
              <div className="executive-point caution">
                <div className="point-icon"><IconBan size={16} /></div>
                <div>
                  <strong>当前规则排除提醒</strong>
                  <p>
                    {result.excluded.map(ex => `${ex.scheme_name}（${ex.failed_rules.length ? ex.failed_rules.join('、') : ex.reason}）`).join('；')} 未参与此次排名。规则与专业出处仍需核定。
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {result && <ComparisonWorkbench key={id} results={results} ranking={result} projectName={project.data?.name ?? '当前项目'}
        selectedSchemeId={selectedSchemeId} onSelectScheme={schemeId => updateContext({ schemeId })}
        roleName={roleNameMap[result.weights_used.role ?? 'custom'] ?? result.weights_used.role_name ?? '当前权重'} updating={rankingPending} onTrace={setTrace} />}

      <div className="dashboard-top">
        <section className="panel radar-panel">
          <div className="section-heading">
            <h2>四维表现</h2>
            <span className="muted">各方案维度得分 / 100</span>
          </div>
          <SchemeRadar results={results} leadingId={topScheme?.scheme_id} />
          <p className="chart-note">点击图例隐藏方案 · 硬约束未通过的方案用虚线显示</p>
        </section>

        <section className="panel rank-panel">
          <div className="section-heading">
            <h2>方案排名</h2>
            <Tooltip title="TOPSIS 逼近理想解排序法：通过计算到理想最优方案的相对距离排定名次，贴近度越接近 1.0 越优。">
              <span className="muted">TOPSIS 贴近度 <IconHelpCircle size={14} style={{ verticalAlign: 'middle' }} /></span>
            </Tooltip>
          </div>
          {result ? <RankingList result={result} /> : ranked.isFetching ? <Skeleton active /> : <Empty description="暂无排序结果" />}
        </section>
      </div>

      <details className="dashboard-scheme-details"><summary>按方案查看完整得分摘要</summary>
      <div className="section-heading result-heading">
        <div>
          <h2>方案一览与依据溯源</h2>
          <p className="section-subtext">点击任一维度得分卡片，即可下钻查看计算公式、条文依据与扣分细节</p>
        </div>
        <span className="muted">确定性计算 · 每分可查</span>
      </div>

      <div className="scheme-cards">{results.map(e => {
        const hardFailures = (e.compliance ?? []).filter(c=>c.status==='failed' && c.severity==='error')
        const incomplete = (e.compliance ?? []).some(c=>c.status==='insufficient_data')
        const entry = result?.ranking.find(r=>r.scheme_id===e.scheme_id)
        const persona = evaluationSummary(e)
        return <article className="panel scheme-card" key={e.scheme_id} style={{borderTopColor:schemeColor(e.scheme_id)}}>
          <div className="scheme-card-top">
            <div><h3 title={e.scheme_name}>{schemeNameParts(e.scheme_name ?? e.scheme_id).title}</h3>
            {schemeNameParts(e.scheme_name ?? '').detail && <small className="name-detail">{schemeNameParts(e.scheme_name ?? '').detail}</small>}</div>
            <span className="persona-badge-tag">{persona.title}</span>
          </div>
          <p className="scheme-persona-desc">{persona.desc}</p>
          <div className="scheme-badges">
            <Tag color={hardFailures.length ? 'error' : incomplete ? 'warning' : 'success'}>
              {hardFailures.length ? '硬约束未通过' : incomplete ? '规则待补充' : '当前规则检查通过'}
            </Tag>
            {entry?.is_non_dominated && <Tag color="blue">非劣方案</Tag>}
          </div>
          <div className="score-grid">{dimensions.map(d=><button className="score-button" key={d.key} onClick={()=>setTrace({evaluation:e,dimension:d.key})}>
            <span style={{color:d.color}}>{d.short}</span><strong>{e.dimension_scores?.[d.key]?.toFixed(1) ?? '—'}</strong>
            <small>覆盖 {((e.dimension_coverage?.[d.key] ?? 0)*100).toFixed(0)}%</small></button>)}</div>
        </article>
      })}</div>
      </details>

      {result?.demo?.warnings.map((warning,i) => <Alert key={i} type="info" showIcon message={warning} />)}

      {result && <div className="analysis-grid">
        <section className="panel">
          <div className="section-heading">
            <h2>权重敏感性分析</h2>
            <Tooltip title="查看给定扰动范围内第一名是否变化。结果反映当前评分与权重假设，不证明方案的工程可靠性。">
              <span className="muted">扰动测试 · 格内为第一名 <IconHelpCircle size={14} style={{ verticalAlign: 'middle' }} /></span>
            </Tooltip>
          </div>
          {!sensitivity ? <Empty description="此组自定义权重暂无离线敏感性快照，请选择角色模板或连接后端" /> : <><div className="sensitivity-table"><table><thead><tr><th>维度 / 扰动</th>{[-.2,-.1,.1,.2].map(d=><th key={d}>{d>0?'+':''}{d*100}%</th>)}</tr></thead>
            <tbody>{dimensions.map(d=><tr key={d.key}><th>{d.label}</th>{[-.2,-.1,.1,.2].map(delta=>{
              const cell=sensitivity.cells.find(c=>c.criterion===d.key && Math.abs(c.delta-delta)<1e-8)
              return <td key={delta} className={cell?.rank_changed ? 'sensitivity-changed' : ''}>{cell ? nameAt(cell.top_index) : '—'}{cell?.rank_changed && <small>排名变化</small>}</td>
            })}</tr>)}</tbody></table></div>
          <div className="flip-summary">{sensitivity.flip_points.map(f=><p key={f.criterion}>
            {dimensions.find(d=>d.key===f.criterion)?.label}：{f.flip_weight==null ? '扫描范围内第一名未改变' :
              '权重扫描至 '+(f.flip_weight*100).toFixed(0)+'% 时，第一名变为 '+nameAt(f.new_top_index)}。</p>)}</div></>}
        </section>

        <section className="panel">
          <div className="section-heading">
            <h2>蒙特卡洛名次概率</h2>
            <Tooltip title="蒙特卡洛抽样：在当前权重附近随机抽取多组权重，保持方案得分不变，统计每个方案获得各名次的频率。结果取决于权重抽样模型。">
              <span className="muted">{acceptability ? acceptability.samples + ' 组权重抽样' : '暂无抽样结果'} <IconHelpCircle size={14} style={{ verticalAlign: 'middle' }} /></span>
            </Tooltip>
          </div>
          {!acceptability ? <Empty description="此组自定义权重暂无离线概率快照，请选择角色模板或连接后端" /> : <RankProbability ranking={result} results={results} />}
        </section>
      </div>}

      <p className="demo-note">{isMock ? '【示例】仅用于交互开发。' : ''}规则、角色矩阵与专业出处仍需核定；当前评分不作为工程安全或合规证明。</p>
    </>}
    <TraceDrawer open={!!trace} evaluation={trace?.evaluation} dimension={trace?.dimension} ruleId={trace?.ruleId} onClose={()=>setTrace(undefined)} />
  </>
}
