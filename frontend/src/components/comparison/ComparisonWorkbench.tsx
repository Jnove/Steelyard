import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent } from 'react'
import type { EvalResult, RankResponse } from '../../api/types'
import { dimensions, type DimensionKey } from '../../constants/dimensions'
import { comparisonRows, comparisonSchemes, dimensionScore, finiteScore, orderSchemes, pairSummary, rowScore, rowStatus, rowValue, scoreDifference, scoreText, signedScore } from '../../utils/comparison'
import type { ComparisonRow, ComparisonScheme, ComparisonSelection, ComparisonView, MatrixDataset, ScoreMode } from '../../utils/comparison'
import { comparisonSvg } from './ComparisonExport'
import { PairPlot, TradeoffPlot } from './ComparisonPlots'
import './comparison-workbench.css'

interface Props {
  results: EvalResult[]
  ranking: RankResponse
  projectName: string
  roleName: string
  updating: boolean
  selectedSchemeId?: string
  onSelectScheme?: (schemeId: string) => void
  onTrace: (selection: { evaluation: EvalResult; dimension?: DimensionKey; ruleId?: string }) => void
}
const views = [{ key: 'map', label: '1. 看整体' }, { key: 'pair', label: '2. 比两套' }, { key: 'matrix', label: '3. 查全表' }] as const
const titles = { map: '把两项关注点，变成一张取舍地图', pair: '选两套方案，逐项看清差多少', matrix: '把比较落到每一项指标' }
const descriptions = { map: '每个点是一套方案。右上方表示两项得分都较高；点击方案，查看它的优势组合。', pair: '四个维度使用同一把尺。右侧差值按“方案一减方案二”计算，点击维度查看依据。', matrix: '筛选方案，展开维度或搜索指标。每一个分数和规则状态，都能继续查到输入与依据。' }
const schemeStyle = (scheme: ComparisonScheme): CSSProperties => ({ '--scheme-color': scheme.color } as CSSProperties)

function Detail({ selection, scheme, ranking, onTrace }: { selection?: ComparisonSelection; scheme?: ComparisonScheme; ranking: RankResponse; onTrace: Props['onTrace'] }) {
  if (!selection || !scheme) return <aside className="comp-detail"><p>选择一个得分或状态，查看对应依据。</p></aside>
  const row = selection.row, metric = row.kind === 'metric' ? scheme.evaluation.metrics?.[row.key] : undefined
  const check = row.kind === 'compliance' ? scheme.evaluation.compliance?.find(item => item.rule_id === row.key) : undefined
  const dimIndex = ranking.criteria.indexOf(row.dimension ?? '')
  const metrics = row.kind === 'dimension' ? Object.values(scheme.evaluation.metrics ?? {}).filter(item => item.dimension === row.dimension) : []
  const score = rowScore(row, scheme)
  return <aside className="comp-detail" aria-label="当前指标详情" style={schemeStyle(scheme)}>
    <p className="comp-kicker">{scheme.name} · {row.kind === 'dimension' ? '维度汇总' : row.key}</p>
    <h3>{row.name}</h3>
    <div className="comp-detail-score">{row.kind === 'compliance' ? rowStatus(row, scheme) : scoreText(score)}{row.kind !== 'compliance' && <small> / 100 分</small>}</div>
    {row.kind === 'dimension' ? <><p>维度分来自后端按适用指标加权汇总。当前角色权重 {dimIndex < 0 ? '—' : ((ranking.weights_used.weights[dimIndex] ?? 0) * 100).toFixed(1) + '%'}。</p>
      <p>数据覆盖率 {finiteScore(scheme.evaluation.dimension_coverage?.[row.dimension!]) ? (scheme.evaluation.dimension_coverage![row.dimension!]! * 100).toFixed(0) + '%' : '—'}。</p>
      <div className="comp-metric-list">{metrics.map(item => <button key={item.rule_id} onClick={() => onTrace({ evaluation: scheme.evaluation, ruleId: item.rule_id })}><span>{item.name}<small>{item.rule_id} · 维度内相对权重 {item.weight_in_dimension ?? '—'}</small></span><strong>{scoreText(item.score)}</strong></button>)}</div>
    </> : <><dl className="comp-detail-facts"><div><dt>{row.kind === 'metric' ? '指标值' : '实际值'}</dt><dd>{rowValue(row, scheme) ?? '—'}</dd></div>
      <div><dt>{row.kind === 'metric' ? '指标状态' : '严重程度'}</dt><dd>{metric ? metric.status === 'not_applicable' ? '不适用' : metric.status === 'insufficient_data' ? '数据不足' : '已评分' : check?.severity === 'warning' ? '警告级' : check ? '错误级' : '数据不足'}</dd></div>
      {check?.limit && <div><dt>条件</dt><dd>{check.limit}</dd></div>}</dl>
      <p className="comp-formula">{metric?.formula ?? check?.formula}</p><p>{check?.message}</p>
      <p className="comp-source">{metric?.source ?? check?.source ?? '暂无依据数据'}</p>
    </>}
    {scheme.excluded && <p className="comp-warning">未参与当前排名，仅供得分与规则参考。</p>}
    <button className="comp-primary" onClick={() => onTrace({ evaluation: scheme.evaluation, dimension: row.dimension, ruleId: row.kind === 'dimension' ? undefined : row.key })}>查看输入、曲线与依据</button>
  </aside>
}

export default function ComparisonWorkbench({ results, ranking, projectName, roleName, updating, onTrace, selectedSchemeId, onSelectScheme }: Props) {
  const schemes = useMemo(() => comparisonSchemes(results, ranking), [results, ranking])
  const ordered = orderSchemes(schemes, 'rank')
  const baseId = ordered[0]?.id ?? ''
  const prefix = useId().replace(/:/g, '')
  const [view, setView] = useState<ComparisonView>('map')
  const [xAxis, setXAxis] = useState<DimensionKey>('quality')
  const [yAxis, setYAxis] = useState<DimensionKey>('construction')
  const [includeExcluded, setIncludeExcluded] = useState(false)
  const [localSelectedId, setLocalSelectedId] = useState(selectedSchemeId ?? baseId)
  const selectedId = selectedSchemeId ?? localSelectedId
  const setSelectedId = (id: string) => { setLocalSelectedId(id); onSelectScheme?.(id) }
  const [pairA, setLocalPairA] = useState(selectedSchemeId ?? baseId)
  const setPairA = (id: string) => { setLocalPairA(id); setSelectedId(id) }
  const [pairB, setPairB] = useState(ordered[1]?.id ?? '')
  const [dataset, setDataset] = useState<MatrixDataset>('scores')
  const [mode, setMode] = useState<ScoreMode>('score')
  const [baselineId, setBaselineId] = useState(baseId)
  const [dimension, setDimension] = useState<DimensionKey | 'all'>('all')
  const [search, setSearch] = useState('')
  const [order, setOrder] = useState<'rank' | 'name'>('rank')
  const [shown, setShown] = useState(() => new Set(schemes.map(scheme => scheme.id)))
  const [expanded, setExpanded] = useState<Set<DimensionKey>>(() => new Set())
  const [selection, setSelection] = useState<ComparisonSelection>()
  const [exporting, setExporting] = useState(false)
  const [notice, setNotice] = useState('')
  const searchInput = useRef<HTMLInputElement>(null)
  const tableScroller = useRef<HTMLDivElement>(null)
  const cells = useRef(new Map<string, HTMLButtonElement>())
  const previousIds = useRef(new Set(schemes.map(scheme => scheme.id)))
  const ids = JSON.stringify(schemes.map(scheme => scheme.id).sort())
  useEffect(() => {
    const nextIds = new Set<string>(JSON.parse(ids))
    const before = previousIds.current
    setShown(current => new Set([...current].filter(id => nextIds.has(id)).concat([...nextIds].filter(id => !before.has(id)))))
    previousIds.current = nextIds
  }, [ids])

  const mapSchemes = schemes.filter(scheme => includeExcluded || !scheme.excluded)
  const selected = mapSchemes.find(scheme => scheme.id === selectedId) ?? mapSchemes.find(scheme => scheme.id === baseId) ?? mapSchemes[0]
  const first = schemes.find(scheme => scheme.id === pairA) ?? ordered[0]
  const second = schemes.find(scheme => scheme.id === pairB && scheme.id !== first?.id) ?? ordered.find(scheme => scheme.id !== first?.id)
  const baseline = schemes.find(scheme => scheme.id === baselineId) ?? ordered[0]
  const displayed = orderSchemes(schemes.filter(scheme => shown.has(scheme.id)), order)
  const rows = comparisonRows(results, dataset, expanded, dimension, search)
  const currentSelection = selection && rows.some(row => row.key === selection.row.key) && displayed.some(scheme => scheme.id === selection.schemeId)
    ? { schemeId: selection.schemeId, row: rows.find(row => row.key === selection.row.key)! } : rows[0] && displayed[0] ? { row: rows[0], schemeId: displayed[0].id } : undefined
  const detailScheme = displayed.find(scheme => scheme.id === currentSelection?.schemeId)
  const allRows = comparisonRows(results, 'scores', new Set(dimensions.map(dim => dim.key)), 'all', '')
  const metricCount = allRows.filter(row => row.kind === 'metric').length
  const ruleCount = comparisonRows(results, 'compliance', new Set(), 'all', '').length
  const plotted = mapSchemes.filter(scheme => dimensionScore(scheme, xAxis) != null && dimensionScore(scheme, yAxis) != null)

  function traceCell(row: ComparisonRow, scheme: ComparisonScheme) {
    setSelectedId(scheme.id)
    setSelection({ row, schemeId: scheme.id })
    if (matchMedia('(max-width: 900px)').matches) onTrace({ evaluation: scheme.evaluation, dimension: row.dimension, ruleId: row.kind === 'dimension' ? undefined : row.key })
  }
  function moveCell(event: KeyboardEvent<HTMLButtonElement>, row: number, column: number) {
    const deltas: Record<string, [number, number]> = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }
    const delta = deltas[event.key]
    if (!delta) return
    event.preventDefault()
    const targetRow = Math.max(0, Math.min(rows.length - 1, row + delta[0]))
    const targetColumn = Math.max(0, Math.min(displayed.length - 1, column + delta[1]))
    const target = cells.current.get(`${rows[targetRow].key}:${displayed[targetColumn].id}`)
    target?.focus({ preventScroll: true })
    setSelection({ row: rows[targetRow], schemeId: displayed[targetColumn].id })
    setSelectedId(displayed[targetColumn].id)
    const scroller = tableScroller.current
    if (target && scroller) {
      const cellRect = target.getBoundingClientRect(), rect = scroller.getBoundingClientRect()
      const header = scroller.querySelector('thead')?.getBoundingClientRect()
      const corner = scroller.querySelector('thead th')?.getBoundingClientRect()
      if (cellRect.right > rect.right) scroller.scrollLeft += cellRect.right - rect.right + 10
      if (cellRect.left < rect.left + (corner?.width ?? 200) + 10) scroller.scrollLeft -= rect.left + (corner?.width ?? 200) + 10 - cellRect.left
      if (cellRect.bottom > rect.bottom) scroller.scrollTop += cellRect.bottom - rect.bottom + 10
      if (cellRect.top < rect.top + (header?.height ?? 88) + 10) scroller.scrollTop -= rect.top + (header?.height ?? 88) + 10 - cellRect.top
    }
  }
  function compareSelected() {
    if (!selected) return
    setPairA(selected.id)
    setPairB(ordered.find(scheme => scheme.id !== selected.id)?.id ?? '')
    setView('pair')
  }
  function resetMatrix() {
    setShown(new Set(schemes.map(scheme => scheme.id))); setDimension('all'); setSearch(''); setOrder('rank')
    setExpanded(new Set()); setMode('score'); setDataset('scores'); setBaselineId(baseId); setSelection(undefined)
  }
  async function exportCurrent() {
    setExporting(true); setNotice('')
    let url: string | undefined
    let link: HTMLAnchorElement | undefined
    try {
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      const scope = view === 'matrix' ? displayed : view === 'pair' ? [first, second].filter((scheme): scheme is ComparisonScheme => !!scheme) : mapSchemes
      const svg = comparisonSvg({ view, projectName, roleName, criteria: ranking.criteria, weights: ranking.weights_used.weights, schemes: scope, xAxis, yAxis, selectedId: selected?.id ?? '', first, second, rows, mode, baseline })
      url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
      link = document.createElement('a'); link.href = url; link.download = `steelyard-comparison-${view}-${new Date().toISOString().slice(0, 10)}.svg`
      document.body.append(link); link.click(); setNotice('已导出当前视图 SVG，包含当前角色与方案范围。')
    } catch { setNotice('导出失败，请重试。') }
    finally { link?.remove(); if (url) { const objectUrl = url; setTimeout(() => URL.revokeObjectURL(objectUrl), 1000) }; setExporting(false) }
  }

  return <section className="comparison-workbench" aria-label="方案比较工作台" aria-busy={updating}>
    <div className="comp-toolbar">
      <div className="comp-tabs" role="tablist" aria-label="方案对比视图">{views.map(item => <button key={item.key} id={`${prefix}-tab-${item.key}`} role="tab" aria-selected={view === item.key} aria-controls={`${prefix}-view`} tabIndex={view === item.key ? 0 : -1}
        onClick={() => { setView(item.key); setNotice('') }} onKeyDown={event => {
          if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); const next = views[(views.findIndex(tab => tab.key === view) + (event.key === 'ArrowRight' ? 1 : 2)) % 3]; setView(next.key); document.getElementById(`${prefix}-tab-${next.key}`)?.focus() }
        }}>{item.label}</button>)}</div>
      <div className="comp-toolbar-end"><span>{roleName}{updating ? ' · 更新中…' : ''}</span><button className="comp-export" disabled={exporting || updating || (view === 'pair' && !second) || (view === 'matrix' && (!rows.length || !displayed.length))} onClick={() => { void exportCurrent() }}>{exporting ? '正在导出…' : '导出当前图'} <small>SVG</small></button></div>
    </div>
    <div className="comp-heading"><h2>{titles[view]}</h2><p>{descriptions[view]}</p></div>
    {notice && <p className="comp-export-status" role="status">{notice}</p>}
    <div id={`${prefix}-view`} role="tabpanel" aria-labelledby={`${prefix}-tab-${view}`}>
      {view === 'map' && <>
        <div className="comp-controls"><label>横轴 <select aria-label="取舍图横轴" value={xAxis} onChange={event => { const next = event.target.value as DimensionKey; if (next === yAxis) setYAxis(xAxis); setXAxis(next) }}>{dimensions.map(dim => <option key={dim.key} value={dim.key}>{dim.label}</option>)}</select></label>
          <label>纵轴 <select aria-label="取舍图纵轴" value={yAxis} onChange={event => { const next = event.target.value as DimensionKey; if (next === xAxis) setXAxis(yAxis); setYAxis(next) }}>{dimensions.map(dim => <option key={dim.key} value={dim.key}>{dim.label}</option>)}</select></label>
          {!!schemes.some(scheme => scheme.excluded) && <label className="comp-checkbox"><input type="checkbox" checked={includeExcluded} onChange={event => setIncludeExcluded(event.target.checked)} />显示未参与排名的方案（仅参考）</label>}
        </div>
        <div className="comp-visual-layout"><div><div className="comp-plot"><TradeoffPlot schemes={mapSchemes} xAxis={xAxis} yAxis={yAxis} selectedId={selected?.id ?? ''} onSelect={setSelectedId} /></div>
          <details className="comp-pareto"><summary>◎ 双环标记：四维非劣方案 · 什么意思？</summary><p>在本次参与排名的方案中，没有另一套方案能在全部四个维度上不差、且至少一项更好。标记直接读取后端四维分析结果；二维点的位置不能代替这个判断。</p></details>
          {plotted.length < mapSchemes.length && <p className="comp-warning">{mapSchemes.length - plotted.length} 套方案缺少当前两轴的可用得分，未绘制点位；可在“查全表”查看缺项。</p>}
          <div className="comp-legend" aria-label="选择取舍图方案">{mapSchemes.map(scheme => <button key={scheme.id} style={schemeStyle(scheme)} aria-pressed={selected?.id === scheme.id} onClick={() => setSelectedId(scheme.id)}><i />{scheme.name}{scheme.excluded && <small>仅参考</small>}</button>)}</div>
        </div>
        {selected ? <aside className="comp-detail" style={schemeStyle(selected)} aria-label="取舍图当前方案"><p className="comp-kicker">当前选中方案</p><h3>{selected.name}</h3>
          <div className="comp-badges"><span>{selected.ranked ? `当前第 ${selected.ranked.rank} 名` : '未参与排名 · 仅参考'}</span>{selected.ranked?.is_non_dominated && <span>四维非劣</span>}</div>
          <div className="comp-score-list">{dimensions.map(dim => <button className="score-button" key={dim.key} onClick={() => onTrace({ evaluation: selected.evaluation, dimension: dim.key })}><span>{dim.label}</span><strong>{scoreText(dimensionScore(selected, dim.key))}<small> 分 ↗</small></strong></button>)}</div>
          <p>当前{roleName}视角{selected.ranked ? `，贴近度 ${selected.ranked.closeness.toFixed(3)}` : `：${selected.reason}`}。二维位置只展示两项差异，完整排序综合四维权重。</p>
          <button className="comp-primary" onClick={compareSelected} disabled={schemes.length < 2}>与另一方案做差值对比</button>
        </aside> : <aside className="comp-detail"><p>当前没有可展示的参与方案。可勾选参考方案，或补充数据后重新评估。</p></aside>}
        </div>
      </>}

      {view === 'pair' && <>
        <div className="comp-controls comp-pair-controls"><label>方案一 <select aria-label="差值图方案一" value={first?.id ?? ''} onChange={event => { if (event.target.value === second?.id) setPairB(first?.id ?? ''); setPairA(event.target.value) }}>{schemes.map(scheme => <option key={scheme.id} value={scheme.id}>{scheme.name}{scheme.excluded ? '（仅参考）' : ''}</option>)}</select></label>
          <button className="comp-secondary" aria-label="交换对比方案" disabled={!second} onClick={() => { setPairA(second?.id ?? ''); setPairB(first?.id ?? '') }}>⇄ 交换</button>
          <label>方案二 <select aria-label="差值图方案二" value={second?.id ?? ''} disabled={!second} onChange={event => { if (event.target.value === first?.id) setPairA(second?.id ?? ''); setPairB(event.target.value) }}>{schemes.map(scheme => <option key={scheme.id} value={scheme.id}>{scheme.name}{scheme.excluded ? '（仅参考）' : ''}</option>)}</select></label>
        </div>
        {first && second ? <><div className="comp-legend">{[first, second].map(scheme => <span key={scheme.id} style={schemeStyle(scheme)}><i />{scheme.name}</span>)}</div>
          {(first.excluded || second.excluded) && <p className="comp-warning">{[first, second].filter(scheme => scheme.excluded).map(scheme => scheme.name).join('、')}未参与当前排名；这里仅比较已返回的得分。</p>}
          <div className="comp-visual-layout"><div className="comp-plot"><PairPlot first={first} second={second} onTrace={dim => onTrace({ evaluation: first.evaluation, dimension: dim })} /></div>
            <aside className="comp-detail" aria-label="双方案差值小结"><p className="comp-kicker">逐项取舍</p><h3>两套方案，差在哪里？</h3><p>{pairSummary(first, second)}</p>
              <div className="comp-pair-values">{dimensions.map(dim => <button key={dim.key} onClick={() => onTrace({ evaluation: first.evaluation, dimension: dim.key })}><span>{dim.label}</span><strong>{signedScore(scoreDifference(dimensionScore(first, dim.key), dimensionScore(second, dim.key)))}</strong></button>)}</div>
              <p>正数表示方案一得分较高，负数表示方案二较高。差值用原始分数做差后显示；缺数据不补零。</p><button className="comp-primary" onClick={() => setView('matrix')}>查完整指标与规则</button>
            </aside></div></> : <p className="comp-empty">还需另一套已评估的方案，才能进行双方案比较。</p>}
      </>}

      {view === 'matrix' && <>
        <div className="comp-matrix-controls"><div className="comp-toggle" role="group" aria-label="矩阵查询内容"><button aria-pressed={dataset === 'scores'} onClick={() => setDataset('scores')}>指标评分 <small>{metricCount}</small></button><button aria-pressed={dataset === 'compliance'} onClick={() => setDataset('compliance')}>合规检查 <small>{ruleCount}</small></button></div>
          <label className="comp-search">搜索指标或规则 <span><input ref={searchInput} type="search" aria-label="搜索指标或规则" placeholder="如：得房率、K-01" value={search} onChange={event => setSearch(event.target.value)} /><button aria-label="清空指标搜索" disabled={!search} onClick={() => { setSearch(''); searchInput.current?.focus() }}>×</button></span></label>
          <label>方案排列 <select aria-label="矩阵方案排列" value={order} onChange={event => setOrder(event.target.value as 'rank' | 'name')}><option value="rank">按当前排名</option><option value="name">按方案名称</option></select></label>
        </div>
        <div className="comp-filter-line"><span>比较方案</span><div className="comp-scheme-filters">{schemes.map(scheme => <label key={scheme.id} style={schemeStyle(scheme)} title={scheme.name}><input type="checkbox" aria-label={`矩阵显示 ${scheme.name}`} checked={shown.has(scheme.id)} onChange={event => setShown(current => { const next = new Set(current); if (event.target.checked) next.add(scheme.id); else next.delete(scheme.id); return next })} /><span>{scheme.name}</span>{scheme.excluded && <small>参考</small>}</label>)}</div><button className="comp-text-button" onClick={resetMatrix}>恢复默认</button></div>
        {dataset === 'scores' && <><div className="comp-filter-line"><div className="comp-dimensions" role="group" aria-label="矩阵维度筛选">{[{ key: 'all', label: '全部维度' }, ...dimensions].map(dim => <button key={dim.key} aria-pressed={dimension === dim.key} onClick={() => setDimension(dim.key as DimensionKey | 'all')}>{dim.label}</button>)}</div><div className="comp-expansion"><button className="comp-text-button" onClick={() => setExpanded(new Set(dimensions.map(dim => dim.key)))}>展开全部指标</button><button className="comp-text-button" onClick={() => setExpanded(new Set())}>收起指标</button></div></div>
          <div className="comp-filter-line"><div className="comp-toggle" role="group" aria-label="矩阵得分显示方式"><button aria-pressed={mode === 'score'} onClick={() => setMode('score')}>看得分</button><button aria-pressed={mode === 'difference'} onClick={() => setMode('difference')}>看与基准的差距</button></div><label>比较基准 <select aria-label="矩阵比较基准" value={baseline?.id ?? ''} disabled={mode === 'score'} onChange={event => setBaselineId(event.target.value)}>{schemes.map(scheme => <option key={scheme.id} value={scheme.id}>{scheme.name}</option>)}</select></label><span className="comp-range-count">{displayed.length} 套方案 · {rows.length} 行结果</span></div></>}
        <div className="comp-matrix-layout">
          {!rows.length || !displayed.length ? <p className="comp-empty">{!displayed.length ? '未选择比较方案，请至少勾选一套方案。' : '没有匹配的指标或规则，请调整搜索条件。'}</p>
            : <div ref={tableScroller} className="comp-table-scroll" tabIndex={0} role="region" aria-label="可滚动的方案指标矩阵"><table className="comp-table" style={{ minWidth: Math.max(650, 200 + displayed.length * 120) }}>
              <caption className="comp-sr-only">{dataset === 'compliance' ? '方案合规检查' : '方案指标评分'} · {roleName}{mode === 'difference' && dataset === 'scores' ? ` · 基准 ${baseline?.name}` : ''}</caption>
              <thead><tr><th scope="col">{dataset === 'compliance' ? '硬约束规则' : '维度 / 评价指标'}<small>{dataset === 'scores' ? '汇总行可展开明细' : '点状态查看检查依据'}</small></th>{displayed.map(scheme => <th key={scheme.id} scope="col" style={schemeStyle(scheme)} className={currentSelection?.schemeId === scheme.id ? 'comp-column-selected' : ''}><div className="comp-scheme-head"><span className="comp-scheme-badge">{scheme.badge}</span><strong title={scheme.name}>{scheme.name}</strong><small>{scheme.ranked ? `第 ${scheme.ranked.rank} 名 · ${scheme.ranked.closeness.toFixed(3)}` : '未参与排名 · 仅参考'}</small></div></th>)}</tr></thead>
              <tbody>{rows.map((row, rowIndex) => <tr key={row.key} className={`comp-row-${row.kind}`}><th scope="row">{row.kind === 'dimension' ? <button className="comp-expand-row" aria-label={`${expanded.has(row.dimension!) ? '收起' : '展开'}${row.name}指标`} aria-expanded={expanded.has(row.dimension!)} onClick={() => setExpanded(current => { const next = new Set(current); if (next.has(row.dimension!)) next.delete(row.dimension!); else next.add(row.dimension!); return next })}><span aria-hidden="true">{expanded.has(row.dimension!) ? '⌄' : '›'}</span><span>{row.name}<small>{row.metricCount} 项指标</small></span></button> : <span>{row.name}<small>{row.key}</small></span>}</th>
                {displayed.map((scheme, column) => {
                  const score = rowScore(row, scheme), delta = scoreDifference(score, rowScore(row, baseline))
                  const active = currentSelection?.schemeId === scheme.id && currentSelection.row.key === row.key
                  const best = Math.max(...displayed.filter(item => !item.excluded).map(item => rowScore(row, item)).filter(finiteScore))
                  const leading = dataset === 'scores' && !scheme.excluded && finiteScore(score) && Math.abs(score - best) < 1e-8
                  const relative = mode === 'difference' && dataset === 'scores'
                  const display = dataset === 'compliance' ? rowStatus(row, scheme) : relative ? delta == null ? score == null ? rowStatus(row, scheme) : '基准缺数据' : signedScore(delta) : score == null ? rowStatus(row, scheme) : scoreText(score)
                  const shownValue = relative ? delta : score
                  return <td key={scheme.id} style={schemeStyle(scheme)} className={scheme.excluded ? 'comp-reference-cell' : ''}>
                    <button ref={element => { const key = `${row.key}:${scheme.id}`; if (element) cells.current.set(key, element); else cells.current.delete(key) }} className={`comp-cell ${active ? 'is-selected' : ''} ${relative && finiteScore(delta) && delta < 0 ? 'is-negative' : ''}`} aria-label={`${scheme.name} · ${row.name} · ${display}${relative ? ' 分差' : dataset === 'scores' ? ' 分' : ''}${scheme.excluded ? ' · 未参与排名，仅参考' : ''}`} aria-pressed={active}
                      onClick={() => traceCell(row, scheme)} onKeyDown={event => moveCell(event, rowIndex, column)}>
                      <strong className={dataset === 'compliance' ? `comp-rule-status status-${scheme.evaluation.compliance?.find(item => item.rule_id === row.key)?.status ?? 'insufficient_data'}` : ''}>{display}</strong>
                      {dataset === 'scores' && finiteScore(shownValue) && <span className={`comp-score-track ${relative ? 'is-difference' : ''}`}><i style={{ width: Math.min(100, Math.abs(shownValue)) / (relative ? 2 : 1) + '%', left: relative ? shownValue < 0 ? (50 - Math.min(100, Math.abs(shownValue)) / 2) + '%' : '50%' : '0' }} /></span>}
                      <small>{row.kind === 'metric' ? `指标值 ${rowValue(row, scheme) ?? '—'}` : row.kind === 'compliance' ? '查看判定依据' : leading ? '已选参与方案中最高' : '维度汇总'}</small>
                    </button></td>
                })}</tr>)}</tbody></table></div>}
          <Detail selection={currentSelection} scheme={detailScheme} ranking={ranking} onTrace={onTrace} />
        </div><p className="comp-table-note">数字为主要读数，短条辅助比较。方向键移动格子；点击查看详情。未参与排名的方案可参考得分，缺数据与不适用分别呈现。</p>
      </>}
    </div>
    <footer className="comp-footer"><span>角色改变权重与排名，四维得分不随角色改写。</span><span>统一评分刻度 0–100 · 专业依据仍需核定</span></footer>
  </section>
}
