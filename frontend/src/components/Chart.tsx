import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { tokens } from '../theme'

export default function Chart({ option, height = 280, label }: { option: EChartsOption; height?: number; label: string }) {
  return <div role="img" aria-label={label}><ReactECharts notMerge option={{
    animationDuration: tokens.duration, textStyle: { fontFamily: tokens.font, fontSize: tokens.small, color: tokens.ink },
    color: tokens.chart, ...option,
  }} style={{ height, width: '100%' }} /></div>
}
