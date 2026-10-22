import { lazy, useEffect, useState } from 'react'
import { Drawer, Skeleton } from 'antd'
import type { EvalResult } from '../api/types'
import { dimensions, type DimensionKey } from '../constants/dimensions'
import DeferredContent from './DeferredContent'

export interface TraceDrawerProps {
  evaluation?: EvalResult; dimension?: DimensionKey; ruleId?: string; open: boolean; onClose: () => void
}
const TraceContent = lazy(() => import('./TraceContent'))

export default function TraceDrawer(props: TraceDrawerProps) {
  const { ruleId, dimension, open, onClose } = props
  const [hasOpened, setHasOpened] = useState(open)
  useEffect(() => { if (open) setHasOpened(true) }, [open])
  const dim = dimensions.find(item => item.key === dimension)
  // Keep the Drawer mounted for its closing animation and focus restoration.
  return <Drawer title={ruleId ? '规则溯源 · ' + ruleId : '评分溯源 · ' + (dim?.label ?? '全部指标')}
    open={open} onClose={onClose} width={560}>
    {(open || hasOpened) && <DeferredContent errorTitle="评分溯源暂时无法加载" fallback={<Skeleton active />}>
      <TraceContent {...props} />
    </DeferredContent>}
  </Drawer>
}
