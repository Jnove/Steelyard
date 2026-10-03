/** 权重是界面输入；0–1 存储，剩余权重按原比例分配。 */
export function redistributeWeights(weights: readonly number[], index: number, value: number): number[] {
  const next = Math.min(1, Math.max(0, value))
  const others = weights.reduce((sum, item, i) => sum + (i === index ? 0 : item), 0)
  return weights.map((item, i) => i === index ? next : others > 0 ? item / others * (1 - next) : (1 - next) / (weights.length - 1))
}
