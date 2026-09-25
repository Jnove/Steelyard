/**
 * 统一请求封装。
 *
 * - baseURL 默认 /api（开发期 Vite 代理，部署期 Nginx 反代）
 * - 自动 JSON 序列化与解析
 * - 失败时抛出带状态码的 Error，便于调用方捕获
 */

export interface ApiError extends Error {
  status: number
  body?: unknown
}

const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api'

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  body?: unknown
  signal?: AbortSignal
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`

  const init: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
    signal,
  }
  if (body !== undefined) {
    init.body = JSON.stringify(body)
  }

  const response = await fetch(url, init)
  if (!response.ok) {
    const err: ApiError = Object.assign(new Error(`HTTP ${response.status}`), {
      status: response.status,
    })
    try {
      err.body = await response.json()
    } catch {
      /* 响应体不是 JSON，忽略 */
    }
    throw err
  }

  // 204 No Content 等空响应直接返回空对象
  const contentLength = response.headers.get('content-length')
  if (response.status === 204 || contentLength === '0') {
    return undefined as T
  }
  return (await response.json()) as T
}