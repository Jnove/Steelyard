/** REST 与 SSE 共享同一地址；子路径随 Vite 的公开 base 一起构建。 */
export function resolveApiBase(base = '/', override?: string): string {
  return (override ?? `${base.replace(/\/$/, '')}/api`).replace(/\/+$/, '')
}

export const API_BASE = resolveApiBase(import.meta.env?.BASE_URL, import.meta.env?.VITE_API_BASE)
