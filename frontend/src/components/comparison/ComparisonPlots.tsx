import { useId } from 'react'
import { dimensions, type DimensionKey } from '../../constants/dimensions'
import { dimensionScore, finiteScore, scoreDifference, scoreText, signedScore, type ComparisonScheme } from '../../utils/comparison'

const ink = '#29433d'
const muted = '#596e6a'
const ticks = [0, 25, 50, 75, 100]
const shorten = (value: string, limit = 18) => Array.from(value).length > limit ? Array.from(value).slice(0, limit).join('') + '…' : value

function Paint({ prefix, schemes }: { prefix: string; schemes: ComparisonScheme[] }) {
  return <defs>
    <linearGradient id={`${prefix}-plane`} x2="1" y2="1"><stop stopColor="#ccefe5" stopOpacity=".78" /><stop offset=".5" stopColor="#ffffff" stopOpacity=".25" /><stop offset="1" stopColor="#e6d6ef" stopOpacity=".7" /></linearGradient>
    <linearGradient id={`${prefix}-rim`} x2=".3" y2="1"><stop stopColor="#ffffff" /><stop offset="1" stopColor="#afc8c0" stopOpacity=".7" /></linearGradient>
    <linearGradient id={`${prefix}-sheen`} x2="0" y2="1"><stop stopColor="#ffffff" stopOpacity=".8" /><stop offset="1" stopColor="#ffffff" stopOpacity="0" /></linearGradient>
    {schemes.map((scheme, index) => <radialGradient key={scheme.id} id={`${prefix}-bead-${index}`} cx="30%" cy="20%" r="85%"><stop stopColor="#ffffff" stopOpacity=".9" /><stop offset=".42" stopColor={scheme.color} stopOpacity=".85" /><stop offset="1" stopColor={scheme.color} /></radialGradient>)}
  </defs>
}

export function TradeoffPlot({ schemes, xAxis, yAxis, selectedId, onSelect }: {
  schemes: ComparisonScheme[]; xAxis: DimensionKey; yAxis: DimensionKey; selectedId: string; onSelect?: (id: string) => void
}) {
  const prefix = 'map-' + useId().replace(/:/g, '')
  const left = 60, top = 55, width = 715, height = 340
  const x = (score: number) => left + width * score / 100
  const y = (score: number) => top + height * (1 - score / 100)
  const points = schemes.flatMap(scheme => {
    const sx = dimensionScore(scheme, xAxis), sy = dimensionScore(scheme, yAxis)
    return finiteScore(sx) && finiteScore(sy) ? [{ scheme, sx, sy, px: x(sx), py: y(sy) }] : []
  })
  const labels: { x: number; y: number; width: number }[] = []
  const collides = (a: { x: number; y: number; width: number }, b: { x: number; y: number; width: number }) => a.x < b.x + b.width + 5 && a.x + a.width + 5 > b.x && a.y < b.y + 30 && a.y + 30 > b.y
  return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 475" role="group" aria-label="二维方案取舍图" fontFamily="Segoe UI, Microsoft YaHei, sans-serif">
    <title>{`${dimensions.find(dim => dim.key === xAxis)?.label}与${dimensions.find(dim => dim.key === yAxis)?.label}二维取舍图`}</title>
    <Paint prefix={prefix} schemes={schemes} />
    <rect x={left} y={top} width={width} height={height} rx="18" fill={`url(#${prefix}-plane)`} stroke={`url(#${prefix}-rim)`} strokeWidth="2" />
    <rect x={left + 1} y={top + 1} width={width - 2} height="90" rx="18" fill={`url(#${prefix}-sheen)`} />
    {ticks.map(tick => <g key={tick}><line x1={x(tick)} y1={top} x2={x(tick)} y2={top + height} stroke="#cadcd7" /><line x1={left} y1={y(tick)} x2={left + width} y2={y(tick)} stroke="#cadcd7" />
      <text x={x(tick)} y={top + height + 25} textAnchor="middle" fill={muted} fontSize="13">{tick}</text><text x={left - 15} y={y(tick) + 5} textAnchor="end" fill={muted} fontSize="13">{tick}</text></g>)}
    <text x={left} y="25" fill={ink} fontSize="14">{dimensions.find(dim => dim.key === yAxis)?.label} / 100 分 ↑</text>
    <text x={left + width} y="456" textAnchor="end" fill={ink} fontSize="14">{dimensions.find(dim => dim.key === xAxis)?.label} / 100 分 →</text>
    {points.map(({ scheme, sx, sy, px, py }) => {
      const text = shorten(scheme.name)
      const labelWidth = Math.min(265, Array.from(text).reduce((length, char) => length + (char.charCodeAt(0) > 255 ? 14 : 8), 16))
      const candidates = [[22,-35], [22,12], [-labelWidth-22,-35], [-labelWidth-22,12], [22,-67], [-labelWidth-22,44]]
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
        <text x={px} y={py + 4} textAnchor="middle" fill={scheme.excluded ? scheme.color : '#ffffff'} fontSize="11" fontWeight="600" pointerEvents="none">{scheme.badge}</text>
        <rect x={box.x} y={box.y} width={box.width} height="28" rx="9" fill={selected ? '#e3f0eb' : '#ffffff'} fillOpacity=".94" />
        <text x={box.x + 8} y={box.y + 19} fill={scheme.color} fontSize="14" fontWeight={selected ? 650 : 500} pointerEvents="none">{text}</text>
      </g>
    })}
    {!points.length && <text x="425" y="220" textAnchor="middle" fill={muted} fontSize="16">当前范围没有可绘制的两维得分</text>}
  </svg>
}

export function PairPlot({ first, second, onTrace }: { first: ComparisonScheme; second: ComparisonScheme; onTrace?: (dimension: DimensionKey) => void }) {
  const prefix = 'pair-' + useId().replace(/:/g, '')
  const left = 154, width = 520, x = (score: number) => left + width * score / 100
  return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 465" role="group" aria-label="双方案四维差值图" fontFamily="Segoe UI, Microsoft YaHei, sans-serif">
    <title>{`${first.name}与${second.name}四维得分差值`}</title>
    <Paint prefix={prefix} schemes={[first, second]} />
    <defs><linearGradient id={`${prefix}-bridge`} gradientUnits="userSpaceOnUse" x1={left} x2={left + width}><stop stopColor={first.color} /><stop offset="1" stopColor={second.color} /></linearGradient></defs>
    <text x="16" y="26" fill={muted} fontSize="14">评价维度</text><text x="770" y="26" textAnchor="middle" fill={muted} fontSize="14">{first.badge} − {second.badge} / 分</text>
    {dimensions.map((dim, index) => {
      const y = 84 + index * 93, a = dimensionScore(first, dim.key), b = dimensionScore(second, dim.key), delta = scoreDifference(a, b)
      const same = finiteScore(delta) && Math.abs(delta) < 1e-8
      return <g key={dim.key} className="comp-pair-row" role={onTrace ? 'button' : undefined} tabIndex={onTrace ? 0 : undefined}
        aria-label={`${dim.label}，${first.name} ${scoreText(a)} 分，${second.name} ${scoreText(b)} 分，差值 ${signedScore(delta)} 分，查看评分依据`}
        onClick={() => onTrace?.(dim.key)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onTrace?.(dim.key) } }}>
        <rect x="5" y={y - 41} width="830" height="83" rx="16" fill={index % 2 === 0 ? `url(#${prefix}-plane)` : '#ffffff'} fillOpacity=".6" stroke={`url(#${prefix}-rim)`} strokeWidth="1.5" />
        <rect x="6" y={y - 40} width="828" height="27" rx="15" fill={`url(#${prefix}-sheen)`} />
        <text x="16" y={y + 5} fill={ink} fontSize="15">{dim.label}</text>
        <line x1={left} x2={left + width} y1={y} y2={y} stroke="#cbdcd7" strokeDasharray="3 4" />
        {ticks.map(tick => <line key={tick} x1={x(tick)} x2={x(tick)} y1={y - 28} y2={y + 28} stroke="#dae6e2" />)}
        {finiteScore(a) && finiteScore(b) && <><line x1={x(a)} x2={x(b)} y1={y} y2={y} stroke={`url(#${prefix}-bridge)`} strokeOpacity=".55" strokeWidth="10" strokeLinecap="round" /><line x1={x(a)} x2={x(b)} y1={y - 2} y2={y - 2} stroke="#ffffff" strokeOpacity=".7" strokeWidth="1.5" /></>}
        {finiteScore(a) && <><circle cx={x(a)} cy={y} r={same ? 12 : 10} fill={`url(#${prefix}-bead-0)`} stroke={first.color} strokeWidth="1.5" /><text x={x(a)} y={y - 20} textAnchor="middle" fill={first.color} fontSize="14">{scoreText(a)}</text></>}
        {finiteScore(b) && <><circle cx={x(b)} cy={y} r={same ? 7 : 10} fill={`url(#${prefix}-bead-1)`} stroke={same ? '#ffffff' : second.color} strokeWidth="1.5" /><text x={x(b)} y={y + 30} textAnchor="middle" fill={second.color} fontSize="14">{scoreText(b)}</text></>}
        <text x="770" y={y + 6} textAnchor="middle" fontSize="20" fontWeight="650" fill={!finiteScore(delta) || same ? muted : delta > 0 ? '#4165a2' : '#93662e'}>{signedScore(delta)}</text>
      </g>
    })}
    {ticks.map(tick => <text key={tick} x={x(tick)} y="422" textAnchor="middle" fill={muted} fontSize="13">{tick}</text>)}
    <text x={left + width} y="451" textAnchor="end" fill={muted} fontSize="13">统一评分刻度 / 0–100</text>
  </svg>
}
