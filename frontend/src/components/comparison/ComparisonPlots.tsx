import { useEffect, useId, useRef, useState } from 'react'
import { dimensions, type DimensionKey } from '../../constants/dimensions'
import { dimensionScore, finiteScore, scoreDifference, scoreText, signedScore, type ComparisonScheme } from '../../utils/comparison'
import { shortSchemeLabel } from '../../utils/presentation-names'

const ink = '#243635'
const muted = '#657572'
const ticks = [0, 25, 50, 75, 100]

// Match SVG coordinates to CSS pixels so a smaller card keeps readable type.
// The initial width also supplies a deterministic canvas for standalone SVG exports.
function usePlotWidth() {
  const ref = useRef<SVGSVGElement>(null)
  const [width, setWidth] = useState(850)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const measure = () => setWidth(Math.max(180, Math.round(element.getBoundingClientRect().width)))
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return { ref, width }
}

function Paint({ prefix, schemes }: { prefix: string; schemes: ComparisonScheme[] }) {
  return <defs>
    <linearGradient id={`${prefix}-plane`}><stop stopColor="#ffffff" /><stop offset="1" stopColor="#ffffff" /></linearGradient>
    <linearGradient id={`${prefix}-rim`}><stop stopColor="#e4eae8" /><stop offset="1" stopColor="#e4eae8" /></linearGradient>
    <linearGradient id={`${prefix}-sheen`}><stop stopColor="#ffffff" stopOpacity="0" /><stop offset="1" stopColor="#ffffff" stopOpacity="0" /></linearGradient>
    {schemes.map((scheme, index) => <radialGradient key={scheme.id} id={`${prefix}-bead-${index}`}><stop stopColor={scheme.color} /><stop offset="1" stopColor={scheme.color} /></radialGradient>)}
  </defs>
}
export function TradeoffPlot({ schemes, xAxis, yAxis, selectedId, onSelect }: {
  schemes: ComparisonScheme[]; xAxis: DimensionKey; yAxis: DimensionKey; selectedId: string; onSelect?: (id: string) => void
}) {
  const prefix = 'map-' + useId().replace(/:/g, '')
  const canvas = usePlotWidth()
  const left = canvas.width < 420 ? 44 : 56, top = 55, width = canvas.width - left - 26, height = 320
  const x = (score: number) => left + width * score / 100
  const y = (score: number) => top + height * (1 - score / 100)
  const points = schemes.flatMap(scheme => {
    const sx = dimensionScore(scheme, xAxis), sy = dimensionScore(scheme, yAxis)
    return finiteScore(sx) && finiteScore(sy) ? [{ scheme, sx, sy, px: x(sx), py: y(sy) }] : []
  })
  const labels: { x: number; y: number; width: number }[] = []
  const collides = (a: { x: number; y: number; width: number }, b: { x: number; y: number; width: number }) => a.x < b.x + b.width + 5 && a.x + a.width + 5 > b.x && a.y < b.y + 30 && a.y + 30 > b.y
  return <svg ref={canvas.ref} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${canvas.width} 450`} role="group" aria-label="二维方案取舍图" fontFamily="Segoe UI, Microsoft YaHei, sans-serif">
    <title>{`${dimensions.find(dim => dim.key === xAxis)?.label}与${dimensions.find(dim => dim.key === yAxis)?.label}二维取舍图`}</title>
    <Paint prefix={prefix} schemes={schemes} />
    <rect x={left} y={top} width={width} height={height} rx="4" fill={`url(#${prefix}-plane)`} stroke={`url(#${prefix}-rim)`} strokeWidth="2" />
    <rect x={left + 1} y={top + 1} width={width - 2} height="90" rx="4" fill={`url(#${prefix}-sheen)`} />
    {ticks.map(tick => <g key={tick}><line x1={x(tick)} y1={top} x2={x(tick)} y2={top + height} stroke="#cadcd7" /><line x1={left} y1={y(tick)} x2={left + width} y2={y(tick)} stroke="#cadcd7" />
      <text x={x(tick)} y={top + height + 25} textAnchor="middle" fill={muted} fontSize="16">{tick}</text><text x={left - 15} y={y(tick) + 5} textAnchor="end" fill={muted} fontSize="16">{tick}</text></g>)}
    <text x={left} y="25" fill={ink} fontSize="16">{dimensions.find(dim => dim.key === yAxis)?.label} / 100 分 ↑</text>
    <text x={left + width} y="435" textAnchor="end" fill={ink} fontSize="16">{dimensions.find(dim => dim.key === xAxis)?.label} / 100 分 →</text>
    {points.map(({ scheme, sx, sy, px, py }) => {
      const text = canvas.width < 420 ? scheme.badge : shortSchemeLabel(scheme.name, scheme.badge)
      const labelWidth = Array.from(text).reduce((length, char) => length + (char.charCodeAt(0) > 255 ? 16 : 9), 16)
      const candidates = [[22,-35], [22,12], [-labelWidth-22,-35], [-labelWidth-22,12], [22,-67], [-labelWidth-22,44], [22,76], [-labelWidth-22,-99], [22,108], [-labelWidth-22,140]]
      const boxes = candidates.map(([dx, dy]) => ({ x: Math.max(left + 5, Math.min(left + width - labelWidth - 5, px + dx)), y: Math.max(32, Math.min(top + height - 30, py + dy)), width: labelWidth }))
      const box = boxes.find(candidate => !labels.some(previous => collides(candidate, previous)) && !points.some(point => collides(candidate, { x: point.px - 18, y: point.py - 18, width: 36 }))) ?? boxes[0]
      labels.push(box)
      const selected = selectedId === scheme.id
      return <g key={scheme.id} className="comp-point" role={onSelect ? 'button' : undefined} tabIndex={onSelect ? 0 : undefined}
        aria-label={`${scheme.name}，${scoreText(sx)} / ${scoreText(sy)} 分${scheme.excluded ? '，未参与排名，仅参考' : scheme.ranked?.is_non_dominated ? '，四维非劣' : ''}`}
        aria-pressed={onSelect ? selected : undefined} onClick={() => onSelect?.(scheme.id)} onKeyDown={event => {
          if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect?.(scheme.id) }
        }}>
        <title>{`${scheme.name} · ${scoreText(sx)} / ${scoreText(sy)} 分`}</title>
        <line x1={px} y1={py} x2={Math.max(box.x, Math.min(box.x + box.width, px))} y2={Math.max(box.y, Math.min(box.y + 28, py))} stroke={scheme.color} strokeOpacity=".45" />
        {selected && <circle cx={px} cy={py} r="25" fill={scheme.color} fillOpacity=".12" />}
        {scheme.ranked?.is_non_dominated && <circle cx={px} cy={py} r="18" fill="none" stroke={scheme.color} strokeWidth="1.5" />}
        <circle className="comp-bead" cx={px} cy={py} r="12" fill={scheme.excluded ? '#ffffff' : `url(#${prefix}-bead-${schemes.indexOf(scheme)})`} stroke={scheme.color} strokeWidth="2" strokeDasharray={scheme.excluded ? '3 2' : undefined} />
        <text x={px} y={py + 4} textAnchor="middle" fill={scheme.excluded ? scheme.color : '#ffffff'} fontSize="14" fontWeight="600" pointerEvents="none">{scheme.badge}</text>
        <rect className="comp-point-label-box" x={box.x} y={box.y} width={box.width} height="28" rx="4" fill={selected ? '#e3f0eb' : '#ffffff'} fillOpacity=".94" />
        <text className="comp-point-label" x={box.x + 8} y={box.y + 19} fill={scheme.color} fontSize="16" fontWeight={selected ? 650 : 500} pointerEvents="none">{text}</text>
      </g>
    })}
    {!points.length && <text x={canvas.width / 2} y="220" textAnchor="middle" fill={muted} fontSize="16">当前范围没有可绘制的两维得分</text>}
  </svg>
}

export function PairPlot({ first, second, onTrace }: { first: ComparisonScheme; second: ComparisonScheme; onTrace?: (dimension: DimensionKey) => void }) {
  const prefix = 'pair-' + useId().replace(/:/g, '')
  const canvas = usePlotWidth(), compact = canvas.width < 540
  const left = compact ? 36 : 128, width = canvas.width - left - (compact ? 36 : 94), x = (score: number) => left + width * score / 100
  return <svg ref={canvas.ref} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${canvas.width} 480`} role="group" aria-label="双方案四维差值图" fontFamily="Segoe UI, Microsoft YaHei, sans-serif">
    <title>{`${first.name}与${second.name}四维得分差值`}</title>
    <Paint prefix={prefix} schemes={[first, second]} />
    <defs><linearGradient id={`${prefix}-bridge`} gradientUnits="userSpaceOnUse" x1={left} x2={left + width}><stop stopColor={first.color} /><stop offset="1" stopColor={second.color} /></linearGradient></defs>
    <text x="16" y="26" fill={muted} fontSize="16">评价维度</text><text x={canvas.width - 16} y="26" textAnchor="end" fill={muted} fontSize="16">{first.badge} − {second.badge} / 分</text>
    {dimensions.map((dim, index) => {
      const y = 90 + index * 98, a = dimensionScore(first, dim.key), b = dimensionScore(second, dim.key), delta = scoreDifference(a, b)
      const same = finiteScore(delta) && Math.abs(delta) < 1e-8
      return <g key={dim.key} className="comp-pair-row" role={onTrace ? 'button' : undefined} tabIndex={onTrace ? 0 : undefined}
        aria-label={`${dim.label}，${first.name} ${scoreText(a)} 分，${second.name} ${scoreText(b)} 分，差值 ${signedScore(delta)} 分，查看评分依据`}
        onClick={() => onTrace?.(dim.key)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onTrace?.(dim.key) } }}>
        <rect x="5" y={y - 45} width={canvas.width - 10} height="91" rx="4" fill={index % 2 === 0 ? `url(#${prefix}-plane)` : '#ffffff'} fillOpacity=".6" stroke={`url(#${prefix}-rim)`} strokeWidth="1.5" />
        <text x="16" y={y + (compact ? -29 : 5)} fill={ink} fontSize="16">{dim.label}</text>
        <line x1={left} x2={left + width} y1={y} y2={y} stroke="#cbdcd7" strokeDasharray="3 4" />
        {ticks.map(tick => <line key={tick} x1={x(tick)} x2={x(tick)} y1={y - 16} y2={y + 28} stroke="#dae6e2" />)}
        {finiteScore(a) && finiteScore(b) && <><line x1={x(a)} x2={x(b)} y1={y} y2={y} stroke={`url(#${prefix}-bridge)`} strokeOpacity=".55" strokeWidth="10" strokeLinecap="round" /><line x1={x(a)} x2={x(b)} y1={y - 2} y2={y - 2} stroke="#ffffff" strokeOpacity=".7" strokeWidth="1.5" /></>}
        {finiteScore(a) && <><circle cx={x(a)} cy={y} r={same ? 12 : 10} fill={`url(#${prefix}-bead-0)`} stroke={first.color} strokeWidth="1.5" /><text x={x(a)} y={y - 20} textAnchor="middle" fill={first.color} fontSize="16">{scoreText(a)}</text></>}
        {finiteScore(b) && <><circle cx={x(b)} cy={y} r={same ? 7 : 10} fill={`url(#${prefix}-bead-1)`} stroke={same ? '#ffffff' : second.color} strokeWidth="1.5" /><text x={x(b)} y={y + 30} textAnchor="middle" fill={second.color} fontSize="16">{scoreText(b)}</text></>}
        <text x={compact ? canvas.width - 16 : canvas.width - 46} y={y + (compact ? -29 : 6)} textAnchor={compact ? 'end' : 'middle'} fontSize="20" fontWeight="650" fill={!finiteScore(delta) || same ? muted : delta > 0 ? '#4165a2' : '#93662e'}>{signedScore(delta)}</text>
      </g>
    })}
    {ticks.map(tick => <text key={tick} x={x(tick)} y="450" textAnchor="middle" fill={muted} fontSize="16">{tick}</text>)}
    <text x={left + width} y="475" textAnchor="end" fill={muted} fontSize="16">统一评分刻度 / 0–100</text>
  </svg>
}
