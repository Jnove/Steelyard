/** 统一 HTTP 请求；业务模块按开关动态加载离线适配器。 */
export const USE_MOCK = import.meta.env?.VITE_USE_MOCK === 'true'
const API_BASE = (import.meta.env?.VITE_API_BASE ?? '/api').replace(/\/$/, '')
export class ApiError extends Error {
  constructor(public readonly status: number, public readonly body?: unknown) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : body
    super(typeof detail === 'string' ? detail : `HTTP ${status}`)
    this.name = 'ApiError'
  }
}
export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  body?: unknown
  signal?: AbortSignal
}
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options
  const multipart = body instanceof FormData
  let response: Response
  try {
    response = await fetch(`${API_BASE}/${path.replace(/^\//, '')}`, {
      method, signal,
      headers: body === undefined || multipart ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : multipart ? body : JSON.stringify(body),
    })
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    throw new ApiError(0, { detail: '无法连接服务，请检查网络或后端状态。' })
  }
  const raw = await response.text()
  let parsed: unknown = undefined
  if (raw) {
    try { parsed = JSON.parse(raw) } catch {
      if (response.ok) throw new ApiError(response.status, { detail: '服务返回了非 JSON 响应。', response: raw })
      parsed = raw
    }
  }
  if (!response.ok) throw new ApiError(response.status, parsed)
  return parsed as T
}
