import type { BuildingModel } from './building-model'
import { tokens } from '../theme'

/** 无 WebGL 时继续使用同一组参数绘制体量，方案选择留在画布外。 */
export default function StaticBuildingStage({ model, label }: { model: BuildingModel; label: string }) {
  const project = (x: number, y: number, z: number) => [290 + (x - z) * 44, 282 + (x + z) * 18 - y * 57]
  const point = (x: number, y: number, z: number) => project(x, y, z).join(',')
  const polygon = (points: number[][]) => points.map(p => point(p[0], p[1], p[2])).join(' ')
  return <svg className="static-building-stage" viewBox="0 0 580 410" role="img" aria-label={label} data-renderer="static">
    <ellipse cx="290" cy="324" rx="203" ry="28" fill={tokens.scene.edge} opacity=".10" />
    <polygon points="40,274 290,176 540,274 290,376" fill={tokens.scene.plate} fillOpacity=".46" stroke={tokens.surface} strokeWidth="2" />
    <polygon points="40,274 290,376 540,274 540,286 290,388 40,286" fill={tokens.scene.facade} fillOpacity=".28" />
    {[...model.volumes].sort((a, b) => (a.x + a.z) - (b.x + b.z)).map((v, index) => {
      const left = v.x - v.width / 2, right = v.x + v.width / 2
      const front = v.z + v.depth / 2, back = v.z - v.depth / 2
      return <g key={index} stroke={tokens.surface} strokeWidth="1.2" strokeOpacity=".8">
        <polygon points={polygon([[left,0,front],[right,0,front],[right,v.height,front],[left,v.height,front]])} fill={tokens.scene.facade} fillOpacity=".86" />
        <polygon points={polygon([[right,0,back],[right,0,front],[right,v.height,front],[right,v.height,back]])} fill={tokens.glowLilac} fillOpacity=".55" />
        <polygon points={polygon([[left,v.height,front],[right,v.height,front],[right,v.height,back],[left,v.height,back]])} fill={tokens.scene.roof} />
        {Array.from({ length: v.floors - 1 }, (_, floor) => {
          const y = (floor + 1) * v.height / v.floors
          return <polyline key={floor} points={polygon([[left,y,front],[right,y,front],[right,y,back]])} fill="none" strokeOpacity=".67" />
        })}
      </g>
    })}
  </svg>
}
