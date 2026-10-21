import { Component, lazy, Suspense, useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Scheme } from '../api/types'
import { buildingModel } from './building-model'
import StaticBuildingStage from './StaticBuildingStage'
import { IconLayers, IconArrowRight } from './Icons'

const BuildingScene = lazy(() => import('./BuildingScene'))
class SceneBoundary extends Component<{ children: ReactNode; fallback: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.props.onFailure() }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

export default function BuildingShowcase({ schemes, pending, failed, onRetry, compact = false }: {
  schemes: Scheme[]; pending: boolean; failed: boolean; onRetry: () => void; compact?: boolean
}) {
  const [selectedId, setSelectedId] = useState<number>()
  const [unavailable, setUnavailable] = useState(false)
  const [ready, setReady] = useState(false)
  const selected = schemes.find(s => s.id === selectedId) ?? schemes[0]
  const model = useMemo(() => buildingModel(selected?.params ?? {}), [selected?.params])
  const onUnavailable = useCallback(() => setUnavailable(true), [])
  const onReady = useCallback(() => setReady(true), [])
  const fallback = <><StaticBuildingStage model={model} label={selected ? `${selected.name} 的静态参数体量示意` : '等待方案参数的展台'} /><span className="stage-mode-note">静态体量示意 · 仍可切换方案</span></>
  const params = selected?.params
  return <section className={'building-showcase' + (compact ? ' building-showcase-compact' : '')} aria-label="建筑体量展台" data-renderer={!model.volumes.length || unavailable ? 'static' : ready ? 'webgl' : 'loading'}>
    <div className="stage-orbit" aria-hidden="true" />
    <div className="stage-heading"><span><IconLayers size={16} />方案展台</span><span className="stage-index">{selected ? `${String(schemes.indexOf(selected) + 1).padStart(2, '0')} / ${String(schemes.length).padStart(2, '0')}` : '待录入'}</span></div>
    <div className="stage-renderer">
      {model.volumes.length && !unavailable ? <SceneBoundary fallback={fallback} onFailure={onUnavailable}>
        <Suspense fallback={<StaticBuildingStage model={model} label="正在载入三维展台" />}><BuildingScene model={model} onUnavailable={onUnavailable} onReady={onReady} /></Suspense>
      </SceneBoundary> : <StaticBuildingStage model={model} label={selected ? `${selected.name} 的参数体量示意` : '等待方案参数的展台'} />}
      {unavailable && <span className="stage-mode-note">静态体量示意 · 仍可切换方案</span>}
      {!model.volumes.length && <div className="stage-empty" role="status">
        <IconLayers size={28} />
        <strong>{pending ? '正在载入候选方案' : failed ? '方案暂未载入' : selected ? '补充参数，展开体量' : '你的下一种选择，从这里开始'}</strong>
        <p>{selected ? `还需录入${model.missing.join('、')}。` : '添加方案后，在这里切换并观察建筑体量。'}</p>
        {failed && <button className="glass-control" type="button" onClick={onRetry}>重新载入 <IconArrowRight size={14} /></button>}
      </div>}
    </div>
    {selected && <div className="stage-float glass-surface" aria-live="polite">
      <div className="stage-float-label">当前展示 <span>{params?.structure_type || '结构待录入'}</span></div>
      <strong title={selected.name}>{selected.name}</strong>
      <p className="stage-character">{model.character}</p>
      <dl className="stage-specs"><div><dt>楼栋</dt><dd>{params?.buildings ?? '—'}<small> 栋</small></dd></div><div><dt>层数</dt><dd>{params?.floors ?? '—'}<small> 层</small></dd></div><div><dt>层高</dt><dd>{params?.floor_height ?? '—'}<small> m</small></dd></div></dl>
    </div>}
    {!!schemes.length && <div className="stage-switcher glass-surface" role="group" aria-label="切换展示方案">{schemes.map((scheme, index) => <button type="button" key={scheme.id} aria-pressed={scheme.id === selected?.id} aria-label={`展示方案 ${scheme.name}`} title={scheme.name} onClick={() => setSelectedId(scheme.id)}><span>{String(index + 1).padStart(2, '0')}</span><span>{scheme.name}</span></button>)}</div>}
    <p className="stage-disclaimer">参数体量示意，不含真实空间布局{model.capped ? ' · 展示已限制楼栋或层数' : ''}<span>{!unavailable && model.volumes.length ? '拖动 / 方向键观察' : '选择方案进行比较'}</span></p>
  </section>
}
