import type { BuildingModel } from './building-model'
import { tokens } from '../theme'

/** 无 WebGL 时继续使用同一组参数绘制体量，方案选择留在画布外。 */
export default function StaticBuildingStage({ model, label }: { model: BuildingModel; label: string }) {
  const project = (x: number, y: number, z: number) => [290 + (x - z) * 44, 282 + (x + z) * 18 - y * 57]
  const point = (x: number, y: number, z: number) => project(x, y, z).join(',')
  const polygon = (points: number[][]) => points.map(p => point(p[0], p[1], p[2])).join(' ')
  const corners = [[40,176], [540,388], ...model.volumes.flatMap(v =>
    [v.x-v.width/2-.08, v.x+v.width/2+.08].flatMap(x => [0,v.height+.08].flatMap(y =>
      [v.z-v.depth/2, v.z+v.depth/2+.12].map(z => project(x,y,z))))) ]
  const minX = Math.min(20, ...corners.map(p => p[0])) - 20, minY = Math.min(20, ...corners.map(p => p[1])) - 20
  const width = Math.max(560, ...corners.map(p => p[0])) + 20 - minX
  const height = Math.max(390, ...corners.map(p => p[1])) + 20 - minY
  return <svg className="static-building-stage" viewBox={`${minX} ${minY} ${width} ${height}`} role="img" aria-label={label} data-renderer="static">
    <ellipse cx="290" cy="324" rx="203" ry="28" fill={tokens.scene.edge} opacity=".10" />
    <polygon points="40,274 290,176 540,274 290,376" fill={tokens.scene.plate} fillOpacity=".46" stroke={tokens.surface} strokeWidth="2" />
    <polygon points="40,274 290,376 540,274 540,286 290,388 40,286" fill={tokens.scene.facade} fillOpacity=".28" />
    {[...model.volumes].sort((a, b) => (a.x + a.z) - (b.x + b.z)).map((v, index) => {
      const left = v.x - v.width / 2, right = v.x + v.width / 2
      const front = v.z + v.depth / 2, back = v.z - v.depth / 2
      return <g key={index} stroke={tokens.surface} strokeWidth="1.2" strokeOpacity=".8">
        <polygon points={polygon([[left,0,front],[right,0,front],[right,v.height,front],[left,v.height,front]])} fill={tokens.scene.building} />
        <polygon points={polygon([[right,0,back],[right,0,front],[right,v.height,front],[right,v.height,back]])} fill={tokens.scene.frame} />
        <polygon points={polygon([[left,v.height,front],[right,v.height,front],[right,v.height,back],[left,v.height,back]])} fill={tokens.scene.roof} />
        {(['南','东'] as const).flatMap(side => {
          const ratio = model.glazing[side]
          if (ratio === null || ratio <= 0) return []
          const bays = side === '南' ? model.bays : Math.max(2, Math.round(model.bays * .65))
          const size = Math.min(.92, Math.sqrt(ratio)), step = v.height / v.floors, pitch = (side === '南' ? v.width : v.depth) / bays
          return Array.from({ length: v.floors * bays }, (_, index) => {
            const floor = Math.floor(index / bays), bay = index % bays
            const along = (side === '南' ? left : back) + (bay + .5) * pitch, y = (floor + .5) * step
            const facePoint = (a: number, h: number) => side === '南' ? [a,h,front] : [right,h,a]
            return <polygon key={`window-${side}-${index}`} data-face={side} points={polygon([
              facePoint(along-pitch*size/2,y-step*size/2), facePoint(along+pitch*size/2,y-step*size/2),
              facePoint(along+pitch*size/2,y+step*size/2), facePoint(along-pitch*size/2,y+step*size/2),
            ])} fill={tokens.scene.facade} stroke="none" />
          })
        })}
        {model.facade !== 'wall' && model.facade !== 'neutral' && Array.from({ length: model.bays + 1 }, (_, bay) => {
          const x = left + bay * v.width / model.bays
          return <polyline key={`rib-${bay}`} points={polygon([[x,0,front],[x,v.height,front]])} fill="none" stroke={model.facade === 'modular' ? tokens.scene.module : tokens.scene.edge} strokeWidth={model.facade === 'hybrid' ? 2 : 1} />
        })}
        {Array.from({ length: v.floors - 1 }, (_, floor) => {
          const y = (floor + 1) * v.height / v.floors
          return <polyline key={floor} points={polygon([[left,y,front],[right,y,front],[right,y,back]])} fill="none" strokeOpacity=".67" />
        })}
        {model.cantilever && [.32,.68].map(fraction => {
          const y = Math.round(v.floors * fraction) * v.height / v.floors
          return <polygon key={fraction} points={polygon([[left-.08,y,front+.12],[right+.08,y,front+.12],[right+.08,y,back],[left-.08,y,back]])} fill={tokens.scene.roof} />
        })}
      </g>
    })}
  </svg>
}
