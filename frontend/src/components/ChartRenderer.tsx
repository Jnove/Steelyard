import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { LineChart, RadarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, MarkPointComponent, RadarComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import { tokens } from '../theme'

echarts.use([LineChart, RadarChart, GridComponent, RadarComponent, LegendComponent, TooltipComponent, MarkPointComponent, CanvasRenderer])

export default function ChartRenderer({ option, height }: { option: EChartsOption; height: number }) {
  return <ReactEChartsCore echarts={echarts} notMerge option={{
    animationDuration: tokens.duration,
    textStyle: { fontFamily: tokens.font, fontSize: tokens.small, color: tokens.ink },
    color: tokens.chart, ...option,
  }} style={{ height, width: '100%' }} />
}
