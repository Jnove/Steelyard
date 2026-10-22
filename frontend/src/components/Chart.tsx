import { lazy } from 'react'
import { Skeleton } from 'antd'
import type { EChartsOption } from 'echarts'
import DeferredContent from './DeferredContent'

const ChartRenderer = lazy(() => import('./ChartRenderer'))

export default function Chart({ option, height = 280, label }: { option: EChartsOption; height?: number; label: string }) {
  return <div role="img" aria-label={label}>
    <DeferredContent errorTitle="图表暂时无法加载" fallback={<div style={{ height }} role="status" aria-label="图表加载中"><Skeleton active /></div>}>
      <ChartRenderer option={option} height={height} />
    </DeferredContent>
  </div>
}
