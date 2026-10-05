import { Alert, Descriptions, Drawer, Empty, Skeleton, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import type { EvalResult } from '../api/types'
import { rules } from '../api/rules'
import { schemes } from '../api/schemes'
import { projects } from '../api/projects'
import { schema } from '../api/schema'
import { dimensions, type DimensionKey } from '../constants/dimensions'
import Chart from './Chart'
import { tokens } from '../theme'

interface Props { evaluation?: EvalResult; dimension?: DimensionKey; ruleId?: string; open: boolean; onClose: () => void }
export default function TraceDrawer({ evaluation, dimension, ruleId, open, onClose }: Props) {
  const projectId = Number(useParams().id)
  const query = useQuery({ queryKey: ['rules'], queryFn: () => rules.get(), enabled: open })
  const inputs = useQuery({ queryKey: ['schemes',projectId], queryFn: () => schemes.list(projectId), enabled: open })
  const project = useQuery({ queryKey: ['project',projectId], queryFn: () => projects.get(projectId), enabled: open })
  const fields = useQuery({ queryKey: ['schema'], queryFn: () => schema.get(), enabled: open })
  const currentParams = inputs.data?.find(s => String(s.id) === evaluation?.scheme_id)?.params
  const params: Record<string,unknown> = { ...project.data?.params, ...currentParams }
  function rawInputs(expression: string): string {
    const names = new Set<string>()
    const visited = new Set<string>()
    function visit(name: string): void {
      if (visited.has(name)) return
      visited.add(name)
      if (Object.hasOwn(params,name)) names.add(name)
      const derived = query.data?.derived_quantities.find(d=>d.name===name)
      derived?.deps.forEach(visit)
    }
    expression.match(/[A-Za-z_][A-Za-z_0-9]*/g)?.forEach(visit)
    return [...names].map(name=>{
      const field = [...(fields.data?.project_params.fields ?? []),...(fields.data?.scheme_params.fields ?? [])].find(f=>f.name===name)
      const value = params[name]
      return (field?.label ?? name) + '：' + (value == null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)) + (field?.unit && field.unit !== '—' ? ' '+field.unit : '')
    }).join('；') || '暂无原始输入'
  }
  const metrics = Object.values(evaluation?.metrics ?? {}).filter(m => ruleId ? m.rule_id === ruleId : m.dimension === dimension)
  const checks = (evaluation?.compliance ?? []).filter(c => c.rule_id === ruleId)
  const dim = dimensions.find(d => d.key === dimension)
  return <Drawer title={ruleId ? '规则溯源 · ' + ruleId : '评分溯源 · ' + (dim?.label ?? '全部指标')}
    open={open} onClose={onClose} width={560}>
    <p className="muted">{evaluation?.scheme_name ?? '当前方案'} · 输入 → 规则 → 得分</p>
    {query.isLoading && <Skeleton active />}
    {query.isError && <Alert type="error" message="评分曲线加载失败" description={query.error.message} />}
    {!metrics.length && !checks.length && <Empty description="暂无对应指标，请先评估方案" />}
    {metrics.map(metric => {
      const definition = query.data?.rules.find(r => r.definition.id === metric.rule_id)?.definition
      const points = definition?.scoring?.points ?? []
      return <section className="trace-item" key={metric.rule_id}>
        <div className="section-heading"><h3>{metric.name}</h3><Tag>{metric.rule_id}</Tag></div>
        <Descriptions size="small" column={1} items={[
          { key: 'raw', label: '原始输入', children: rawInputs(definition?.value ?? metric.formula) },
          { key: 'value', label: '指标值', children: metric.value ?? '—' },
          { key: 'score', label: '得分', children: metric.score == null ? '—（数据不足或不适用）' : metric.score.toFixed(2) + ' / 100' },
          { key: 'formula', label: '计算公式', children: <code>{metric.formula}</code> },
          { key: 'weight', label: '维度内权重', children: metric.weight_in_dimension ?? 1 },
          { key: 'source', label: '依据', children: metric.source },
        ]} />
        {!!metric.missing_fields?.length && <Alert type="warning" message={'缺少字段：' + metric.missing_fields.join('、')} />}
        {points.length > 0 && <Chart height={200} label={metric.name + '评分分段与当前值'} option={{
          grid: { left: 38, right: 20, top: 28, bottom: 35 }, tooltip: { trigger: 'axis' },
          xAxis: { type: 'value', name: '指标值', nameLocation: 'middle', nameGap: 24 },
          yAxis: { type: 'value', min: 0, max: 100, name: '得分' },
          series: [{ type: 'line', data: points, symbolSize: 5, lineStyle: { color: tokens.primary },
            markPoint: metric.value != null && metric.score != null ? { symbol: 'circle', symbolSize: 12,
              itemStyle: { color: tokens.danger }, data: [{ coord: [metric.value, metric.score], name: '当前值' }],
              label: { show: false } } : undefined }],
        }} />}
        {metric.source.includes('TODO') && <p className="muted">【示例】专业依据待专业组确认，当前仅用于开发演示。</p>}
      </section>
    })}
    {checks.map(check => <section className="trace-item" key={check.rule_id}>
      <h3>{check.name}</h3><Alert type={check.status === 'failed' ? 'error' : 'info'} message={check.message} />
      <Descriptions column={1} items={[
        { key: 'value', label: '原始值', children: check.value ?? '—' },
        { key: 'limit', label: '条件', children: check.limit ?? '—' },
        { key: 'formula', label: '判定公式', children: <code>{check.formula}</code> },
        { key: 'source', label: '依据', children: check.source ?? 'TODO(专业组)' },
      ]} />
    </section>)}
  </Drawer>
}
