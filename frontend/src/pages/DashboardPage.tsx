import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Segmented, Skeleton, Slider, Tag, Tooltip } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { evaluation } from '../api/evaluation'
import { ranking } from '../api/ranking'
import { projects } from '../api/projects'
import type { EvalResult, RankResponse } from '../api/types'
import { dimensions, type DimensionKey, isMock } from '../constants/dimensions'
import { tokens } from '../theme'
import { redistributeWeights } from '../utils/weights'
import Chart from '../components/Chart'
import TraceDrawer from '../components/TraceDrawer'
import {
  IconAlertTriangle,
  IconArrowRight,
  IconAward,
  IconBan,
  IconCheck,
  IconHelpCircle,
  IconMessage,
  IconUser,
} from '../components/Icons'

type RankInput = { role: string } | { weights: number[] }

function getSchemePersona(name: string): { title: string; desc: string } {
  if (name.includes('A') || name.includes('高品质')) {
    return { title: '品质旗舰', desc: '大层高·高得房率·工友施工难度大' }
  }
  if (name.includes('B') || name.includes('不合规')) {
    return { title: '红线拦截', desc: '层高<3.0m·违反好房子建设硬指标' }
  }
  if (name.includes('C') || name.includes('MiC')) {
    return { title: 'MiC 装配典范', desc: '装配率75%·极致标准化·工友施工最安全' }
  }
  if (name.includes('D') || name.includes('均衡')) {
    return { title: '稳妥均衡型', desc: '常规现浇框剪·各项指标中规中矩' }
  }
  if (name.includes('E') || name.includes('被支配')) {
    return { title: '劣势淘汰', desc: '各维度均落后于主流方案·无帕累托优势' }
  }
  return { title: '候选方案', desc: '多准则综合评价比选对象' }
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
      const persona = getSchemePersona(s.scheme_name)
      return (
        <div className={'ranking-row ' + (s.rank === 1 ? 'ranking-first' : '')} key={s.scheme_id} data-scheme={s.scheme_id}>
          <span className="rank-number">{String(s.rank).padStart(2, '0')}</span>
          <div className="rank-detail">
            <div className="rank-line">
              <span>
                <strong>{s.scheme_name}</strong>
                <small className="persona-inline-tag">{persona.title}</small>
              </span>
              <span className="numeric">{s.closeness.toFixed(3)}</span>
            </div>
            <div className="rank-track"><div style={{ width: s.closeness * 100 + '%' }} /></div>
          </div>
        </div>
      )
    })}
    {result.excluded.map(s => <div key={s.scheme_id} className="excluded-row">
      <div className="excluded-header">
        <IconBan size={15} style={{ color: 'var(--color-danger)' }} />
        <strong>{s.scheme_name} · 未参与排名（红线排除）</strong>
      </div>
      <p>{s.failed_rules.length ? '硬约束未通过：'+s.failed_rules.join('、') : s.reason}</p>
    </div>)}
  </div>
}

export default function DashboardPage() {
  const { id: rawId } = useParams()
  const id = Number(rawId)
  const [role, setRole] = useState('government')
  const [weights, setWeights] = useState([.25,.25,.25,.25])
  const [request, setRequest] = useState<RankInput>({ role: 'government' })
  const [debounced, setDebounced] = useState<RankInput>(request)
  const [trace, setTrace] = useState<{ evaluation: EvalResult; dimension: DimensionKey }>()
  const project = useQuery({ queryKey: ['project',id], queryFn: () => projects.get(id) })
  const evaluated = useQuery({ queryKey: ['evaluation',id], queryFn: () => evaluation.get(id) })
  const roles = useQuery({ queryKey: ['roles',id], queryFn: () => ranking.roles(id) })
  useEffect(() => { const timer = setTimeout(() => setDebounced(request), 150); return () => clearTimeout(timer) }, [request])
  useEffect(() => {
    const preset = roles.data?.roles.find(r => r.role === role)
    if (preset) setWeights(preset.weights)
  }, [roles.data,role])
  useEffect(() => {
    setRole('government'); setRequest({ role: 'government' }); setDebounced({role:'government'})
    setTrace(undefined)
  }, [id])
  const ranked = useQuery({
    queryKey: ['rank',id,debounced], queryFn: () => ranking.run(id,debounced),
    enabled: !!evaluated.data?.results.length,
    placeholderData: (previous,query) => query?.queryKey[1] === id ? previous : undefined,
  })
  const results = evaluated.data?.results ?? []
  const result = ranked.data
  const sensitivity = result?.sensitivity
  const acceptability = result?.rank_acceptability
  const roleChange = (value: string | number) => {
    const key = String(value); setRole(key)
    setRequest(key === 'custom' ? { weights } : { role: key })
  }
  const changeWeight = (index: number, value: number) => {
    const next = redistributeWeights(weights,index,value / 100)
    setWeights(next); setRole('custom'); setRequest({ weights: next })
  }
  const inputOrder = result?.scheme_order ?? []
  const nameAt = (index: number | null) => index == null ? '—' :
    results.find(e => e.scheme_id === inputOrder[index])?.scheme_name ?? '—'
  const error = evaluated.error ?? roles.error ?? ranked.error
  const ahp = result?.weights_used.ahp

  // 动态提炼推荐结论
  const topScheme = result?.ranking?.[0]
  const topEval = results.find(e => e.scheme_id === topScheme?.scheme_id)
  const excludedCount = result?.excluded?.length ?? 0

  const roleNameMap: Record<string, string> = {
    government: '政府 / 保障房平台',
    developer: '开发企业',
    contractor: '施工总包 / 工友安全',
    resident: '业主 / 住户',
    custom: '自定义专家权重',
  }

  return <>
    <div className="page-heading">
      <div>
        <p className="eyebrow">筑衡 · 多维量化比选</p>
        <h1>方案对比看板</h1>
        <p className="page-description">{project.data?.name ?? '正在加载项目'} · 调整关注重点，观察方案间的动态取舍与决策建议</p>
      </div>
      <div className="action-row">
        <Link to={'/projects/'+id+'/schemes'}><Button>编辑方案</Button></Link>
        <Link to={'/projects/'+id+'/chat'}><Button type="primary">讨论与报告 <IconArrowRight size={15} style={{ verticalAlign: 'middle', marginLeft: 4 }} /></Button></Link>
      </div>
    </div>

    {error && <Alert showIcon type="error" message="评估或排序数据未就绪" description={error.message}
      action={<Button onClick={() => { void evaluated.refetch(); void roles.refetch(); void ranked.refetch() }}>重试</Button>} />}
    {evaluated.isLoading && <Skeleton active paragraph={{ rows: 9 }} />}
    {evaluated.isSuccess && !results.length && <div className="panel"><Empty description="还没有评估结果，请先录入方案并开始评估"><Link to={'/projects/'+id+'/schemes'}><Button type="primary">去录入方案</Button></Link></Empty></div>}

    {!!results.length && <>
      {/* 核心决策简报 (Executive Recommendation Card) */}
      {result && topScheme && (
        <section className="panel executive-summary-card" aria-label="决策建议简报">
          <div className="executive-card-header">
            <div className="executive-lead-title">
              <div className="executive-badge">
                <IconAward size={16} />
                <span>优先推荐方案</span>
              </div>
              <h2>{topScheme.scheme_name}</h2>
              <div className="executive-submeta">
                <Tag color="blue">当前视角：{roleNameMap[role] ?? role}</Tag>
                <Tag color="green">综合排名第 01 名</Tag>
                <span className="executive-metric">TOPSIS 贴近度：<strong>{topScheme.closeness.toFixed(4)}</strong></span>
              </div>
            </div>
            <div className="executive-actions">
              <Link to={`/projects/${id}/chat`}>
                <Button type="primary" size="large">
                  <IconMessage size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                  向 AI 追问推荐依据
                </Button>
              </Link>
            </div>
          </div>

          <div className="executive-points-grid">
            <div className="executive-point positive">
              <div className="point-icon"><IconCheck size={16} /></div>
              <div>
                <strong>推荐主要优势</strong>
                <p>
                  {topEval?.dimension_scores?.construction && topEval.dimension_scores.construction > 70
                    ? `施工友好与工友安全突出（${topEval.dimension_scores.construction.toFixed(1)}分），得益于高标准化重复率与装配化设计，大幅减少现场高空危大工程。`
                    : topEval?.dimension_scores?.quality && topEval.dimension_scores.quality > 80
                    ? `居住品质表现优异（${topEval.dimension_scores.quality.toFixed(1)}分），层高与采光达标，保障居民得房率与居住舒适度。`
                    : `在当前多准则权重设定下，各项指标均好性最强，整体逼近正理想解程度最高。`}
                </p>
              </div>
            </div>

            <div className="executive-point trade-off">
              <div className="point-icon"><IconAlertTriangle size={16} /></div>
              <div>
                <strong>需要接受的取舍</strong>
                <p>
                  {topScheme.scheme_name.includes('MiC') || topScheme.scheme_name.includes('C')
                    ? '标准化模块套型使套内得房率（76%）略低于现浇剪力墙方案（82%），设计阶段需严格把控构件开模规格。'
                    : topScheme.scheme_name.includes('A')
                    ? '大悬挑与舒适空间带来更高的施工安全隐患与现场作业量，施工友好度得分有所牺牲。'
                    : '该方案属于平衡折衷选型，未在单一维度达到极致峰值，需综合权衡各项投入。'}
                </p>
              </div>
            </div>

            {excludedCount > 0 && (
              <div className="executive-point caution">
                <div className="point-icon"><IconBan size={16} /></div>
                <div>
                  <strong>红线规则拦截提醒</strong>
                  <p>
                    {result.excluded.map(ex => `${ex.scheme_name}（${ex.failed_rules.length ? ex.failed_rules.join('、') : ex.reason}）`).join('；')} 已在规范合规初筛阶段被红线拦截，不参与综合选优。
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* 决策视角切换栏 */}
      <div className="role-bar">
        <span className="role-bar-label">
          <IconUser size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          <strong>决策视角</strong>
        </span>
        <Segmented value={role} onChange={roleChange} options={[
          { label: '政府', value: 'government' },
          { label: '开发企业', value: 'developer' },
          { label: '施工总包', value: 'contractor' },
          { label: '住户', value: 'resident' },
          { label: '自定义', value: 'custom' },
        ]} />
        <span className="role-state" aria-live="polite">{ranked.isFetching ? '正在更新排名…' : '权重合计 100%'}</span>
      </div>

      <div className="dashboard-top">
        <section className="panel weights-panel">
          <div className="section-heading">
            <h2>评价权重</h2>
            <Tooltip title="层次分析法（AHP）基于各维度两两对比矩阵计算权重，自定义视角则直接配置滑杆。">
              <span className="help-icon-wrap"><IconHelpCircle size={15} /></span>
            </Tooltip>
          </div>
          <p className="muted">拖动一个维度，其余按比例调整。</p>
          {dimensions.map((d,i) => <div className="weight-control" key={d.key}>
            <div className="weight-label"><span><i style={{ background:d.color }} />{d.label}</span><strong className="numeric">{(weights[i]*100).toFixed(1)}<small>%</small></strong></div>
            <Slider min={0} max={100} step={1} value={weights[i]*100} onChange={v => changeWeight(i,v)} ariaLabelForHandle={d.label+'权重'}
              tooltip={{ formatter: v => v?.toFixed(1)+'%' }} />
          </div>)}
          <div className="consistency">
            <span className="consistency-title">
              一致性 CR
              <Tooltip title="一致性比率 CR < 0.1 表示专家的重要性判断矩阵自洽、无逻辑矛盾。">
                <IconHelpCircle size={13} style={{ marginLeft: 4, verticalAlign: 'middle' }} />
              </Tooltip>
            </span>
            <strong>{role === 'custom' ? '—' : ahp?.cr.toFixed(4) ?? '—'}</strong>
            <p>{role === 'custom' ? '直接赋权，无两两比较矩阵' : ahp ? ahp.consistent ? '一致性检验通过（判断自洽）' : '模板需复核' : '等待角色模板'}</p>
          </div>
          {result?.weights_used.consistency_warning && <Alert type="warning" message={result.weights_used.consistency_warning} />}
          {result?.weights_used.note && <p className="muted caption">{result.weights_used.note}</p>}
        </section>

        <section className="panel radar-panel">
          <div className="section-heading">
            <h2>四维表现</h2>
            <span className="muted">各方案维度得分 / 100</span>
          </div>
          <Chart height={330} label="各方案四维得分雷达图" option={{
            tooltip: {}, legend: { bottom: 0, type:'scroll' }, radar: {
              center:['50%','45%'], radius:'63%', indicator: dimensions.map(d => ({name:d.label,max:100})),
              axisName: {color:tokens.ink}, splitArea:{show:false}, splitLine:{lineStyle:{color:tokens.border}},
            }, series: [{ type:'radar', data: results.map((e,i) => ({
              name:e.scheme_name || e.scheme_id, value:dimensions.map(d => e.dimension_scores?.[d.key] ?? 0),
              lineStyle:{type: (e.compliance ?? []).some(c=>c.status==='failed' && c.severity==='error') ? 'dashed' : 'solid',width:2},
              itemStyle:{color:tokens.chart[i % tokens.chart.length]}, areaStyle:{opacity:.04}, symbolSize:4,
            })) }],
          }} /><p className="chart-note">点击图例隐藏方案 · 不合规方案用虚线显示</p>
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

      <div className="section-heading result-heading">
        <div>
          <h2>方案一览与依据溯源</h2>
          <p className="section-subtext">点击任一维度得分卡片，即可下钻查看计算公式、条文依据与扣分细节</p>
        </div>
        <span className="muted">确定性计算 · 每分可查</span>
      </div>

      <div className="scheme-cards">{results.map((e,i) => {
        const hardFailures = (e.compliance ?? []).filter(c=>c.status==='failed' && c.severity==='error')
        const incomplete = (e.compliance ?? []).some(c=>c.status==='insufficient_data')
        const entry = result?.ranking.find(r=>r.scheme_id===e.scheme_id)
        const persona = getSchemePersona(e.scheme_name || e.scheme_id)
        return <article className="panel scheme-card" key={e.scheme_id} style={{borderTopColor:tokens.chart[i%tokens.chart.length]}}>
          <div className="scheme-card-top">
            <h3>{e.scheme_name}</h3>
            <span className="persona-badge-tag">{persona.title}</span>
          </div>
          <p className="scheme-persona-desc">{persona.desc}</p>
          <div className="scheme-badges">
            <Tag color={hardFailures.length ? 'error' : incomplete ? 'warning' : 'success'}>
              {hardFailures.length ? '硬约束未通过' : incomplete ? '合规待补充' : '合规检查通过'}
            </Tag>
            {entry?.is_non_dominated && <Tag color="blue">非劣方案</Tag>}
          </div>
          <div className="score-grid">{dimensions.map(d=><button className="score-button" key={d.key} onClick={()=>setTrace({evaluation:e,dimension:d.key})}>
            <span style={{color:d.color}}>{d.short}</span><strong>{e.dimension_scores?.[d.key]?.toFixed(1) ?? '—'}</strong>
            <small>覆盖 {((e.dimension_coverage?.[d.key] ?? 0)*100).toFixed(0)}%</small></button>)}</div>
        </article>
      })}</div>

      {result?.demo?.warnings.map((warning,i) => <Alert key={i} type="info" showIcon message={warning} />)}

      {result && <div className="analysis-grid">
        <section className="panel">
          <div className="section-heading">
            <h2>权重敏感性分析</h2>
            <Tooltip title="测试当某维度权重向上或向下变动 10%~20% 时，第一名是否保持稳定。若不变，说明推荐方案非常稳健。">
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
            <Tooltip title="在权重微小扰动下模拟数百次抽样，统计各方案取得不同排名的频率，客观呈现抗不确定性能力。">
              <span className="muted">{acceptability ? acceptability.samples + ' 组权重抽样' : '暂无抽样结果'} <IconHelpCircle size={14} style={{ verticalAlign: 'middle' }} /></span>
            </Tooltip>
          </div>
          {!acceptability ? <Empty description="此组自定义权重暂无离线概率快照，请选择角色模板或连接后端" /> : <Chart label="方案获得各名次的概率" height={260} option={{
            tooltip:{trigger:'axis',axisPointer:{type:'shadow'}}, legend:{bottom:0},
            grid:{left:105,right:20,top:16,bottom:60},
            xAxis:{type:'value',min:0,max:1,axisLabel:{formatter:(v:number)=>Math.round(v*100)+'%'}},
            yAxis:{type:'category',data:inputOrder.map((_,i)=>nameAt(i)),inverse:true},
            series:acceptability.probabilities[0]?.map((_,rank)=>({
              name:'第 '+(rank+1)+' 名',type:'bar' as const,stack:'probability',barMaxWidth:30,
              data:acceptability.probabilities.map(row=>row[rank]),
            })) ?? [],
          }} />}
          <p className="chart-note">反映权重变化时排名的稳定性，不代表建筑质量的统计置信度。</p>
        </section>
      </div>}

      {isMock && <p className="demo-note">【示例】仅用于交互开发。规则、角色矩阵与方案数据仍需专业组确认。</p>}
    </>}
    <TraceDrawer open={!!trace} evaluation={trace?.evaluation} dimension={trace?.dimension} onClose={()=>setTrace(undefined)} />
  </>
}
