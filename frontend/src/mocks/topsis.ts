import type { TopsisResult } from '../api/types'

/** 仅供演示：在引擎原始维度分上重算 TOPSIS，不在浏览器重写规则评分。 */
export function topsis(scores: number[][], weights: number[]): TopsisResult {
  if (!scores.length) return { schemes: [], ideal_best: weights.map(() => 0), ideal_worst: weights.map(() => 0), weights }
  const norms = weights.map((_, j) => Math.hypot(...scores.map(row => row[j])) || 1)
  const weighted = scores.map(row => row.map((value, j) => value / norms[j] * weights[j]))
  const ideal_best = weights.map((_, j) => Math.max(...weighted.map(row => row[j])))
  const ideal_worst = weights.map((_, j) => Math.min(...weighted.map(row => row[j])))
  const schemes = weighted.map((row, index) => {
    const distance_to_best = Math.hypot(...row.map((v, j) => v - ideal_best[j]))
    const distance_to_worst = Math.hypot(...row.map((v, j) => v - ideal_worst[j]))
    const total = distance_to_best + distance_to_worst
    return { index, distance_to_best, distance_to_worst, closeness: total ? distance_to_worst / total : 0.5, rank: 1 }
  })
  for (const row of schemes) row.rank = 1 + schemes.filter(other => other.closeness > row.closeness + 1e-9).length
  return { schemes, ideal_best, ideal_worst, weights }
}
