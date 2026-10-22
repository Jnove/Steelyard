import { Empty } from 'antd'
import type { EvalResult, RankResponse } from '../api/types'
import { schemeColor } from '../theme'
import { schemeNameParts } from '../utils/presentation-names'

const percent = (value: number) => (value * 100).toFixed(1).replace(/\.0$/, '') + '%'
const validProbability = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1

/** Probability rows follow scheme_order, which is independent of the current rank order. */
export default function RankProbability({ ranking, results }: { ranking: RankResponse; results: EvalResult[] }) {
  const distribution = ranking.rank_acceptability
  if (!distribution) return <Empty description="此组权重暂无名次分布数据" />
  if (!ranking.scheme_order.length) return <Empty description="暂无参与排名的方案" />
  const top = ranking.ranking[0]
  const topIndex = top ? ranking.scheme_order.indexOf(top.scheme_id) : -1
  const firstPlace = distribution.probabilities[topIndex]?.[0]

  return <figure className="rank-probability" aria-label="方案获得各名次的概率">
    <figcaption>
      <p>保持方案得分不变，在当前权重附近抽取 {distribution.samples} 组权重，每组重新排序。</p>
      {top && validProbability(firstPlace) && <p className="probability-summary"><strong title={top.scheme_name}>{schemeNameParts(top.scheme_name).title}</strong> 在其中 <strong>{percent(firstPlace)}</strong> 的抽样中排第一。</p>}
    </figcaption>
    <ol className="probability-schemes">
      {ranking.scheme_order.map((id, index) => {
        const name = results.find(result => result.scheme_id === id)?.scheme_name ?? id
        const probabilities = distribution.probabilities[index]
        const color = schemeColor(id)
        return <li key={id} data-scheme={id}>
          <div className="probability-scheme"><i aria-hidden="true" style={{ background: color }} /><strong title={name}>{schemeNameParts(name).title}</strong></div>
          {probabilities?.length ? <dl className="probability-ranks" style={{ gridTemplateColumns: `repeat(${Math.min(probabilities.length, 5)}, minmax(0, 1fr))` }}>
            {probabilities.map((probability, rank) => <div key={rank} data-rank={rank + 1} data-probability={probability}>
              <dt>第 {rank + 1} 名</dt>
              <dd><span className="numeric">{validProbability(probability) ? percent(probability) : '—'}</span>
                <span className="probability-track" aria-hidden="true"><i style={{ width: validProbability(probability) ? `${probability * 100}%` : 0, background: color }} /></span>
              </dd>
            </div>)}
          </dl> : <p className="muted">名次分布数据缺失</p>}
        </li>
      })}
    </ol>
    <p className="probability-note">每行展示一个方案的名次分布。它反映排名对权重变化的敏感程度，不是方案客观最优或工程安全的概率。</p>
  </figure>
}
