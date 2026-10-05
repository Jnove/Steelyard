import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Segmented, Skeleton, Slider, Tag } from 'antd'
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

type RankInput = { role: string } | { weights: number[] }
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
    {result.ranking.map(s => <div className={'ranking-row ' + (s.rank === 1 ? 'ranking-first' : '')} key={s.scheme_id} data-scheme={s.scheme_id}>
      <span className="rank-number">{String(s.rank).padStart(2, '0')}</span>
      <div className="rank-detail"><div className="rank-line"><strong>{s.scheme_name}</strong><span className="numeric">{s.closeness.toFixed(3)}</span></div>
        <div className="rank-track"><div style={{ width: s.closeness * 100 + '%' }} /></div>
      </div>
    </div>)}
    {result.excluded.map(s => <div key={s.scheme_id} className="excluded-row"><strong>{s.scheme_name} · 未参与排名</strong><p>{s.failed_rules.length ? '硬约束未通过：'+s.failed_rules.join('、') : s.reason}</p></div>)}
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
  return <>
    <div className="page-heading"><div><p className="eyebrow">02 / 多维决策</p><h1>方案对比看板</h1><p className="page-description">{project.data?.name ?? '正在加载项目'} · 调整关注重点，观察方案间的取舍</p></div>
      <div className="action-row"><Link to={'/projects/'+id+'/schemes'}><Button>编辑方案</Button></Link><Link to={'/projects/'+id+'/chat'}><Button type="primary">讨论与报告 →</Button></Link></div>
    </div>
    {error && <Alert showIcon type="error" message="评估或排序数据未就绪" description={error.message}
      action={<Button onClick={() => { void evaluated.refetch(); void roles.refetch(); void ranked.refetch() }}>重试</Button>} />}
    {evaluated.isLoading && <Skeleton active paragraph={{ rows: 9 }} />}
    {evaluated.isSuccess && !results.length && <div className="panel"><Empty description="还没有评估结果，请先录入方案并开始评估"><Link to={'/projects/'+id+'/schemes'}><Button type="primary">去录入方案</Button></Link></Empty></div>}
    {!!results.length && <>
      <div className="role-bar"><span className="muted">决策视角</span><Segmented value={role} onChange={roleChange} options={[
        { label:'政府',value:'government' },{ label:'开发企业',value:'developer' },
        { label:'施工总包',value:'contractor' },{ label:'住户',value:'resident' },{ label:'自定义',value:'custom' },
      ]} /><span className="role-state" aria-live="polite">{ranked.isFetching ? '正在更新排名…' : '权重合计 100%'}</span></div>
      <div className="dashboard-top">
        <section className="panel weights-panel"><div className="section-heading"><h2>评价权重</h2><span className="muted">四维度</span></div>
          <p className="muted">拖动一个维度，其余按比例调整。</p>
          {dimensions.map((d,i) => <div className="weight-control" key={d.key}>
            <div className="weight-label"><span><i style={{ background:d.color }} />{d.label}</span><strong className="numeric">{(weights[i]*100).toFixed(1)}<small>%</small></strong></div>
            <Slider min={0} max={100} step={1} value={weights[i]*100} onChange={v => changeWeight(i,v)} ariaLabelForHandle={d.label+'权重'}
              tooltip={{ formatter: v => v?.toFixed(1)+'%' }} />
          </div>)}
          <div className="consistency"><span>一致性 CR</span><strong>{role === 'custom' ? '—' : ahp?.cr.toFixed(4) ?? '—'}</strong>
            <p>{role === 'custom' ? '直接赋权，无两两比较矩阵' : ahp ? ahp.consistent ? '一致性检验通过' : '模板需复核' : '等待角色模板'}</p></div>
          {result?.weights_used.consistency_warning && <Alert type="warning" message={result.weights_used.consistency_warning} />}
          {result?.weights_used.note && <p className="muted caption">{result.weights_used.note}</p>}
        </section>
        <section className="panel radar-panel"><div className="section-heading"><h2>四维表现</h2><span className="muted">维度得分 / 100</span></div>
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
        <section className="panel rank-panel"><div className="section-heading"><h2>方案排名</h2><span className="muted">TOPSIS 贴近度</span></div>
          {result ? <RankingList result={result} /> : ranked.isFetching ? <Skeleton active /> : <Empty description="暂无排序结果" />}
        </section>
      </div>
      <div className="section-heading result-heading"><h2>方案一览</h2><span className="muted">点击维度分数，查看每一步计算依据</span></div>
      <div className="scheme-cards">{results.map((e,i) => {
        const hardFailures = (e.compliance ?? []).filter(c=>c.status==='failed' && c.severity==='error')
        const incomplete = (e.compliance ?? []).some(c=>c.status==='insufficient_data')
        const entry = result?.ranking.find(r=>r.scheme_id===e.scheme_id)
        return <article className="panel scheme-card" key={e.scheme_id} style={{borderTopColor:tokens.chart[i%tokens.chart.length]}}>
          <h3>{e.scheme_name}</h3><div className="scheme-badges"><Tag color={hardFailures.length ? 'error' : incomplete ? 'warning' : 'success'}>{hardFailures.length ? '硬约束未通过' : incomplete ? '合规待补充' : '合规检查通过'}</Tag>{entry?.is_non_dominated && <Tag color="blue">非劣方案</Tag>}</div>
          <div className="score-grid">{dimensions.map(d=><button className="score-button" key={d.key} onClick={()=>setTrace({evaluation:e,dimension:d.key})}>
            <span style={{color:d.color}}>{d.short}</span><strong>{e.dimension_scores?.[d.key]?.toFixed(1) ?? '—'}</strong>
            <small>覆盖 {((e.dimension_coverage?.[d.key] ?? 0)*100).toFixed(0)}%</small></button>)}</div>
        </article>
      })}</div>
      {result?.demo?.warnings.map((warning,i) => <Alert key={i} type="info" showIcon message={warning} />)}
      {result && <div className="analysis-grid">
        <section className="panel"><div className="section-heading"><h2>权重敏感性</h2><span className="muted">格内为第一名方案</span></div>
          {!sensitivity ? <Empty description="此组自定义权重暂无离线敏感性快照，请选择角色模板或连接后端" /> : <><div className="sensitivity-table"><table><thead><tr><th>维度 / 扰动</th>{[-.2,-.1,.1,.2].map(d=><th key={d}>{d>0?'+':''}{d*100}%</th>)}</tr></thead>
            <tbody>{dimensions.map(d=><tr key={d.key}><th>{d.label}</th>{[-.2,-.1,.1,.2].map(delta=>{
              const cell=sensitivity.cells.find(c=>c.criterion===d.key && Math.abs(c.delta-delta)<1e-8)
              return <td key={delta} className={cell?.rank_changed ? 'sensitivity-changed' : ''}>{cell ? nameAt(cell.top_index) : '—'}{cell?.rank_changed && <small>排名变化</small>}</td>
            })}</tr>)}</tbody></table></div>
          <div className="flip-summary">{sensitivity.flip_points.map(f=><p key={f.criterion}>
            {dimensions.find(d=>d.key===f.criterion)?.label}：{f.flip_weight==null ? '扫描范围内第一名未改变' :
              '权重扫描至 '+(f.flip_weight*100).toFixed(0)+'% 时，第一名变为 '+nameAt(f.new_top_index)}。</p>)}</div></>}
        </section>
        <section className="panel"><div className="section-heading"><h2>名次概率</h2><span className="muted">{acceptability ? acceptability.samples + ' 组权重抽样' : '暂无抽样结果'}</span></div>
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
