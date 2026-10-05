import type { NumberIssue } from './agents'
import type { ChatStreamEvent } from './sse'

export interface ToolCall {
  id: string; name: string; status: 'running' | 'done' | 'interrupted'; result?: unknown
}
export interface StreamContent {
  content: string
  tools: ToolCall[]
  unverifiedNumbers: NumberIssue[]
  citationWarning?: boolean
  cached?: boolean
}

/** 只把 done 里的校验位置用于最终正文；草稿警告的偏移不可沿用。 */
export function applyAgentEvent<T extends StreamContent>(state: T, event: ChatStreamEvent): T {
  if (event.type === 'token') return { ...state,
    content: event.replace ? event.text : state.content + event.text,
    ...(event.replace ? { unverifiedNumbers: [], citationWarning: false } : {}),
  }
  if (event.type === 'citation_warning') return { ...state, citationWarning: true }
  if (event.type === 'done') return { ...state,
    content: event.report ?? state.content, unverifiedNumbers: event.unverified_numbers ?? [],
    citationWarning: (event.unverified_numbers?.length ?? 0) > 0, cached: event.cached,
    tools: state.tools.map(tool => tool.status === 'running' ? { ...tool, status: 'interrupted' } : tool),
  }
  if (event.type === 'tool_start' || event.type === 'tool_end') {
    const tool: ToolCall = { id: event.id, name: event.name,
      status: event.type === 'tool_end' ? 'done' : 'running',
      result: event.type === 'tool_end' ? event.result : undefined }
    return { ...state, tools: state.tools.some(entry => entry.id === tool.id)
      ? state.tools.map(entry => entry.id === tool.id ? tool : entry) : [...state.tools, tool] }
  }
  return state
}

/** Python 字符偏移按 Unicode 码点切分，不能按 JavaScript UTF-16 下标切分。 */
export function numberSegments(text: string, issues: NumberIssue[]) {
  const characters = Array.from(text)
  const result: { text: string; unverified: boolean }[] = []
  let cursor = 0
  for (const issue of [...issues].sort((a, b) => a.start - b.start)) {
    if (issue.start < cursor || issue.end > characters.length) continue
    result.push({ text: characters.slice(cursor, issue.start).join(''), unverified: false })
    result.push({ text: characters.slice(issue.start, issue.end).join(''), unverified: true })
    cursor = issue.end
  }
  result.push({ text: characters.slice(cursor).join(''), unverified: false })
  return result
}
