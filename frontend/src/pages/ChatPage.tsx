import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Alert, Button, Collapse, Empty, Input, InputNumber, Progress, Select, Skeleton, Tag } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import Markdown from 'react-markdown'
import { Link, useParams } from 'react-router-dom'
import { evaluation } from '../api/evaluation'
import { ranking } from '../api/ranking'
import { rules } from '../api/rules'
import type { EvalResult } from '../api/types'
import type { AgentRequest, SchemeChange } from '../api/generated/AgentRequest'
import { mockSSE, postSSE, streamDelay } from '../api/sse'
import { API_BASE } from '../api/base'
import { ApiError } from '../api/client'
import { applyAgentEvent, numberSegments, type StreamContent, type ToolCall } from '../api/agent-state'
import TraceDrawer from '../components/TraceDrawer'
import { IconFileText } from '../components/Icons'
import { planRequest, suggestedQuestions, type PlanResponse } from '../api/agents'
import { offlineQuestions } from '../utils/suggested-questions'
import { decisionInput, decisionLabel } from '../utils/decision-context'
import { useDecisionContext } from '../utils/use-decision-context'
import { plannedRequest, previewValue } from '../utils/agent-plan'

type DimensionKey = 'quality' | 'structure' | 'construction' | 'green'
type Ranking = Awaited<ReturnType<typeof ranking.run>>['ranking']
type RuleCatalog = Awaited<ReturnType<typeof rules.get>>
type StreamStatus = 'streaming' | 'done' | 'cancelled' | 'error'
interface ChatMessage extends StreamContent {
  id: number
  role: 'user' | 'assistant'
  kind: 'chat' | 'report'
  content: string
  status: StreamStatus
  schemeId?: string
  decisionLabel?: string
  tools: ToolCall[]
  error?: string
  retryPreview?: { message: string; change: SchemeChange }
}

const isMock = import.meta.env.VITE_USE_MOCK === 'true'
const dimensions: { key: DimensionKey; label: string }[] = [
  { key: 'quality', label: '居住品质' }, { key: 'structure', label: '结构安全' },
  { key: 'construction', label: '施工友好' }, { key: 'green', label: '绿色低碳' },
]
const statusLabels: Record<string, string> = {
  passed: '通过', failed: '未通过', insufficient_data: '数据不足', not_applicable: '不适用', scored: '已评分',
}
const displayNumber = (value: number | null | undefined, digits = 2) =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '暂无数据'
const escapeMarkdown = (value: string) => value.replace(/[\\`*_{}\[\]()<>#+.!|~-]/g, '\\$&').replace(/[\r\n]+/g, ' ')

/** 确定性的演示文本；所有数值均取自查询返回的数据。 */
function mockNarrative(kind: 'chat' | 'report', question: string, results: EvalResult[], ranks: Ranking,
  catalog: RuleCatalog | undefined, schemeId?: string) {
  const current = results.find((item) => item.scheme_id === (/第一/.test(question) ? ranks[0]?.scheme_id : schemeId)) ?? results[0]
  const lines = [kind === 'report' ? '# 方案比选报告（本地 Mock 演示）' : '### 本地 Mock 演示回答',
    '> 内容根据已返回的演示评估与排序数据整理；未调用大模型，未重新执行评估。', '']
  if (kind === 'report' || /第一|排名|排序/.test(question)) {
    lines.push('## 当前决策视角排序', '')
    if (!ranks.length) lines.push('暂无已返回的排序数据，不能判断领先方案。')
    for (const row of [...ranks].sort((a, b) => a.rank - b.rank).slice(0, 1)) {
      lines.push(`- 第 ${row.rank} 名：${escapeMarkdown(row.scheme_name)}，TOPSIS 贴近度 ${displayNumber(row.closeness, 4)}。`)
    }
    lines.push('', '贴近度与名次来自排序接口；仅凭这些结果不能归因于某一项参数，也不能据此推断全部合规。', '')
  }
  if (/如果|假设|提高|降低|what.?if/i.test(question)) {
    lines.push('## What-if 示意（未计算、未写入）', '',
      '这里仅展示讨论调整参数的流程：确认参数及目标值，再由评估与排序接口计算新结果。当前回答未创建副本、未修改方案、未计算变化后的得分或排名。',
      '以下仅列出当前已返回的数据，不能用于预测提高装配率后的结果。', '')
  }
  if (!current) lines.push('当前项目没有已返回的评估结果，请先在方案管理页完成评估。')
  const included = current ? [current] : []
  for (const result of included) {
    lines.push(`## ${escapeMarkdown(result.scheme_name || result.scheme_id)}`, '')
    for (const dimension of dimensions) {
      const coverage = result.dimension_coverage?.[dimension.key]
      lines.push(`- ${dimension.label}：${displayNumber(result.dimension_scores?.[dimension.key])} / 100；数据覆盖率 ${typeof coverage === 'number' ? displayNumber(coverage * 100) + '%' : '暂无数据'}。`)
    }
    lines.push('', '### 已返回的规则结果', '')
    if (!result.compliance?.length) lines.push('未返回合规检查项。')
    for (const check of (result.compliance ?? []).filter(check => check.status === 'failed' || check.status === 'insufficient_data').slice(0, 2)) {
      lines.push(`- ${check.rule_id} ${escapeMarkdown(check.name)}：${statusLabels[check.status] ?? check.status}。${escapeMarkdown(check.message)}`)
    }
    for (const metric of Object.values(result.metrics ?? {}).slice(0, 1)) {
      lines.push(`- ${metric.rule_id} ${escapeMarkdown(metric.name)}：${displayNumber(metric.score)}${metric.score == null ? '' : ' / 100'}；${metric.status ? statusLabels[metric.status] : '状态未返回'}。`)
    }
    lines.push('')
  }
  const pending = catalog?.todo_source_ids ?? []
  if (pending.length) lines.push('部分规则出处仍待专业确认，完整清单见溯源。', '')
  if (!catalog) lines.push('规则目录未加载，无法核对出处是否已确认。', '')
  lines.push('点击正文中的规则编号可查看对应方案的评估依据；本演示不补充未返回的规范条文、限值或因果结论。')
  return lines.join('\n')
}

// 仅转换 Markdown 文本节点，跳过原始 HTML、代码、图片及已有链接。
interface MarkdownNode { type: string; value?: string; url?: string; children?: MarkdownNode[] }
interface TraceOptions { evaluations: EvalResult[]; preferredSchemeId?: string }
function ruleOwner(ruleId: string, options: TraceOptions, preferredSchemeId = options.preferredSchemeId) {
  const candidates = options.evaluations.filter((item) => item.compliance?.some((check) => check.rule_id === ruleId)
    || Object.values(item.metrics ?? {}).some((metric) => metric.rule_id === ruleId))
  // 明确提到的方案保持原有归属，即使该方案尚缺少此规则的评估结果。
  return options.evaluations.find((item) => item.scheme_id === preferredSchemeId) ?? candidates[0]
}
function remarkRuleLinks(options: TraceOptions & { knownRuleIds: Set<string> }) {
  return (tree: MarkdownNode) => {
    const textOf = (node: MarkdownNode): string => node.value ?? node.children?.map(textOf).join('') ?? ''
    function schemeIn(node: MarkdownNode) {
      const text = textOf(node)
      const matches = options.evaluations.filter((item) => item.scheme_name && text.includes(item.scheme_name))
      return matches.length === 1 ? matches[0].scheme_id : undefined
    }
    function visit(node: MarkdownNode, context?: string) {
      if (['link', 'linkReference', 'code', 'inlineCode', 'html', 'image', 'imageReference'].includes(node.type)) return
      if (!node.children) return
      let section = context
      const children: MarkdownNode[] = []
      for (const child of node.children) {
        if (child.type === 'heading') section = schemeIn(child) ?? section
        const localScheme = schemeIn(child) ?? section
        if (child.type !== 'text' || !child.value) {
          visit(child, localScheme)
          children.push(child)
          continue
        }
        const pattern = /\b[A-Z][A-Z0-9]*-\d{2,}\b/g
        let last = 0
        for (const match of child.value.matchAll(pattern)) {
          if (!options.knownRuleIds.has(match[0])) continue
          const index = match.index ?? 0
          if (index > last) children.push({ type: 'text', value: child.value.slice(last, index) })
          const owner = ruleOwner(match[0], options, localScheme ?? options.preferredSchemeId)
          children.push({ type: 'link', url: `#trace/${encodeURIComponent(owner?.scheme_id ?? '')}/${encodeURIComponent(match[0])}`,
            children: [{ type: 'text', value: match[0] }] })
          last = index + match[0].length
        }
        if (last < child.value.length) children.push({ type: 'text', value: child.value.slice(last) })
      }
      node.children = children
    }
    visit(tree, options.preferredSchemeId)
  }
}

function errorMessage(error: unknown) { return error instanceof Error ? error.message : String(error) }
function toolResultText(result: unknown) {
  return typeof result === 'string' ? result : JSON.stringify(result, null, 2) ?? '工具未返回详情'
}
function finishTools(tools: ToolCall[]) {
  return tools.map((tool) => tool.status === 'running' ? { ...tool, status: 'interrupted' as const } : tool)
}

export default function ChatPage() {
  const { id = '' } = useParams<{ id: string }>()
  const projectId = Number(id)
  if (!Number.isSafeInteger(projectId) || projectId <= 0) return <Alert type="error" message="项目 ID 无效" />
  // 项目变化时重新挂载对话，清空记录并取消旧项目的请求。
  return <ProjectChat key={projectId} projectId={projectId} />
}

function ProjectChat({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient()
  const [context, updateContext] = useDecisionContext(projectId)
  const rankInput = decisionInput(context)
  const evaluationQuery = useQuery({ queryKey: ['evaluation', projectId], queryFn: () => evaluation.get(projectId),
    enabled: !!projectId, retry: false })
  const rankingQuery = useQuery({ queryKey: ['rank', projectId, rankInput],
    queryFn: () => ranking.run(projectId, rankInput), enabled: !!projectId,
    retry: false, staleTime: 60_000, refetchOnWindowFocus: false })
  const rulesQuery = useQuery({ queryKey: ['rules'], queryFn: () => rules.get(), retry: false })
  const results = evaluationQuery.data?.results ?? []
  const knownRuleIds = new Set([
    ...(rulesQuery.data?.rules.map((rule) => rule.definition.id) ?? []),
    ...results.flatMap((item) => [
      ...(item.compliance ?? []).map((check) => check.rule_id),
      ...Object.values(item.metrics ?? {}).map((metric) => metric.rule_id),
    ]),
  ])
  const ranks = [...(rankingQuery.data?.ranking ?? [])].sort((a, b) => a.rank - b.rank)
  const [whatifValue, setWhatifValue] = useState<number | null>(null)
  const schemeId = results.find((item) => item.scheme_id === context.schemeId)?.scheme_id
    ?? results.find((item) => item.scheme_id === ranks[0]?.scheme_id)?.scheme_id ?? results[0]?.scheme_id
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [planning, setPlanning] = useState(false)
  const [planError, setPlanError] = useState<string>()
  const [pendingPlan, setPendingPlan] = useState<{ request: AgentRequest; response: PlanResponse }>()
  const pendingRef = useRef(false)
  const planningRequest = useRef<AbortController>()
  const [trace, setTrace] = useState<{ schemeId?: string; ruleId: string; dimension?: DimensionKey }>()
  const active = useRef<{ controller: AbortController; messageId: number }>()
  const nextId = useRef(0)
  const feed = useRef<HTMLDivElement>(null)
  const preview = useRef<HTMLElement>(null)
  const followStream = useRef(true)

  // 卸载提交阶段立即使旧流失效，不等待普通 effect 清理。
  useLayoutEffect(() => () => {
    const previous = active.current
    active.current = undefined
    previous?.controller.abort()
    planningRequest.current?.abort()
    planningRequest.current = undefined
  }, [])
  useEffect(() => {
    if (followStream.current && feed.current) feed.current.scrollTop = feed.current.scrollHeight
  }, [messages])
  useEffect(() => {
    if (pendingPlan) preview.current?.scrollIntoView({ block: 'center', behavior: 'auto' })
  }, [pendingPlan])

  const mockReady = evaluationQuery.isSuccess && !rankingQuery.isPending && !rulesQuery.isPending
  const canStart = !!projectId && !busy && !planning && !pendingPlan && !evaluationQuery.isPending && !rankingQuery.isPending && (!isMock || mockReady)
  const freshSuggestions = useRef(false)
  const suggestionQuery = useQuery({
    queryKey: ['suggestions', projectId, schemeId, evaluationQuery.dataUpdatedAt, rankingQuery.dataUpdatedAt],
    queryFn: ({ signal }) => {
      const refresh = freshSuggestions.current
      freshSuggestions.current = false
      return isMock ? Promise.resolve({ questions: offlineQuestions(results, schemeId), source: 'fake' as const })
        : suggestedQuestions(projectId, schemeId, signal, refresh)
    },
    enabled: !busy && !planning && !pendingPlan && !evaluationQuery.isPending && !rankingQuery.isPending,
    staleTime: Infinity, retry: false, refetchOnWindowFocus: false,
  })
  const currentEvaluation = results.find((item) => item.scheme_id === trace?.schemeId)

  function openTrace(ruleId: string, ownerId?: string) {
    if (!knownRuleIds.has(ruleId)) return
    const owner = ruleOwner(ruleId, { evaluations: results, preferredSchemeId: ownerId ?? schemeId })
    const metric = Object.values(owner?.metrics ?? {}).find((item) => item.rule_id === ruleId)
    setTrace({ schemeId: owner?.scheme_id, ruleId, dimension: metric?.dimension })
  }

  function cancel() {
    if (planningRequest.current) {
      planningRequest.current.abort()
      planningRequest.current = undefined
      setPlanning(false)
      return
    }
    const run = active.current
    if (!run) return
    active.current = undefined
    run.controller.abort()
    setBusy(false)
    setMessages((previous) => previous.map((item) => item.id === run.messageId
      ? { ...item, status: 'cancelled', tools: finishTools(item.tools) } : item))
  }

  function requestBody(message: string, change?: SchemeChange): AgentRequest {
    return { message, ...rankInput, scheme_id: schemeId ? Number(schemeId) : undefined,
      history: messages.filter(item => item.status === 'done').slice(-50)
        .map(item => ({ role: item.role, content: item.content.slice(0, 30_000) })),
      ...(change ? { intent: 'whatif' as const, change } : {}) }
  }

  async function prepare(question = input, change?: SchemeChange) {
    const message = question.trim()
    if (!canStart || active.current || planningRequest.current || pendingRef.current || !message) return
    if (isMock) { void start('chat', message); return }
    const controller = new AbortController()
    planningRequest.current = controller
    setPlanning(true)
    setPlanError(undefined)
    try {
      const body = requestBody(message, change)
      const response = await planRequest(projectId, body, controller.signal)
      if (controller.signal.aborted || planningRequest.current !== controller) return
      const request = plannedRequest(body, response)
      planningRequest.current = undefined
      setPlanning(false)
      if (response.plan.intent === 'whatif') {
        pendingRef.current = true
        setPendingPlan({ request, response })
        setInput('')
      } else {
        void start('chat', message, undefined, request)
      }
    } catch (error) {
      if (!controller.signal.aborted) setPlanError(errorMessage(error))
    } finally {
      if (planningRequest.current === controller) {
        planningRequest.current = undefined
        setPlanning(false)
      }
    }
  }

  async function start(kind: 'chat' | 'report', question = input, change?: SchemeChange, confirmedRequest?: AgentRequest) {
    const message = question.trim()
    // ref 同步拦截重复提交，覆盖 React 尚未更新按钮禁用状态的间隙。
    if (((!canStart || pendingRef.current) && !confirmedRequest) || active.current || planningRequest.current || (kind === 'chat' && !message)) return
    const userId = ++nextId.current
    const messageId = ++nextId.current
    const controller = new AbortController()
    const run = { controller, messageId }
    active.current = run
    setBusy(true)
    setPlanError(undefined)
    followStream.current = true
    if (kind === 'chat') setInput('')
    const messageSchemeId = confirmedRequest?.change?.scheme_id != null ? String(confirmedRequest.change.scheme_id) : schemeId
    setMessages((previous) => [...previous,
      { id: userId, role: 'user', kind, content: kind === 'report' ? '生成 Markdown 比选报告' : message,
        status: 'done', schemeId: messageSchemeId, tools: [], unverifiedNumbers: [] },
      { id: messageId, role: 'assistant', kind, content: '', status: 'streaming', schemeId: messageSchemeId,
        decisionLabel: decisionLabel(confirmedRequest?.intent === 'reweight'
          ? { ...context, role: confirmedRequest.weights ? 'custom' : confirmedRequest.role ?? context.role, weights: confirmedRequest.weights ?? undefined }
          : context), tools: [], unverifiedNumbers: [] },
    ])
    const update = (apply: (item: ChatMessage) => ChatMessage) => {
      if (active.current !== run || controller.signal.aborted) return
      // React 延后执行更新时，再次丢弃已取消请求排队中的内容。
      setMessages((previous) => controller.signal.aborted ? previous
        : previous.map((item) => item.id === messageId ? apply(item) : item))
    }
    try {
      const base = API_BASE
      const events = isMock
        ? mockSSE(mockNarrative(kind, message, results, ranks, rulesQuery.data, schemeId),
          { mock: true, evaluation_count: results.length, ranking: ranks, note: '读取查询结果，未执行新的评估或写入' }, controller.signal)
        : postSSE(`${base}/projects/${encodeURIComponent(projectId)}/${kind}`,
          kind === 'chat' ? { ...(confirmedRequest ?? { ...requestBody(message, change), intent: 'explain' }) }
            : { ...rankInput }, controller.signal)
      let completed = false
      let pendingText = ''
      const flushText = async () => {
        if (!pendingText) return
        const text = pendingText
        pendingText = ''
        if (isMock) await streamDelay(kind === 'report' ? 16 : 8, controller.signal)
        update((item) => applyAgentEvent(item, { type: 'token', text }))
      }
      for await (const event of events) {
        if (active.current !== run || controller.signal.aborted) break
        if (event.type === 'token') {
          if (event.replace) {
            pendingText = ''
            update(item => applyAgentEvent(item, { ...event, text: '' }))
          }
          // 真实流跟随后端 token 刷新；演示按小批刷新，规则扩充后长报告仍能及时完成。
          for (const character of event.text) {
            pendingText += character
            if (pendingText.length >= (isMock ? kind === 'report' ? 128 : 16 : 64)) await flushText()
          }
          if (!isMock) await flushText()
        } else if (event.type === 'tool_start' || event.type === 'tool_end') {
          update(item => applyAgentEvent(item, event))
          if (!isMock && event.type === 'tool_end' && event.result && typeof event.result === 'object') {
            if (event.name === 'evaluate') queryClient.setQueryData(['evaluation', projectId], event.result)
            // 工具排序可能包含副本，不能写入正式方案的排序查询缓存。
          }
        } else if (event.type === 'citation_warning') {
          update(item => applyAgentEvent(item, event))
        } else if (event.type === 'error') {
          await flushText()
          if (event.status) throw new ApiError(event.status, { detail: event.message || '流式接口返回错误' })
          throw new Error(event.message || '流式接口返回错误')
        } else if (event.type === 'done') {
          await flushText()
          completed = true
          update((item) => ({ ...applyAgentEvent(item, event), status: 'done' }))
          // 后端可能创建副本或重新评估；回到看板时读取本次的结果。
          if (!isMock) {
            for (const key of ['evaluation', 'rank', 'schemes']) {
              void queryClient.invalidateQueries({ queryKey: [key, projectId], refetchType: 'none' })
            }
            if (confirmedRequest?.intent === 'reweight') {
              updateContext(confirmedRequest.weights
                ? { role: 'custom', weights: confirmedRequest.weights }
                : { role: confirmedRequest.role ?? context.role, weights: undefined })
            }
          }
          break
        }
      }
      if (!completed && active.current === run && !controller.signal.aborted) throw new Error('流式响应未正常完成')
    } catch (error) {
      if (!controller.signal.aborted) {
        update((item) => ({ ...item, status: 'error', error: errorMessage(error), tools: finishTools(item.tools),
          ...(error instanceof ApiError && error.status === 409 && confirmedRequest?.change
            ? { retryPreview: { message, change: confirmedRequest.change } } : {}) }))
      }
    } finally {
      if (active.current === run) {
        active.current = undefined
        setBusy(false)
      }
    }
  }

  function downloadReport(message: ChatMessage) {
    const partial = message.status !== 'done'
    const text = partial ? `> 未完成报告：${message.status === 'cancelled' ? '用户已停止生成' : '生成发生错误'}，以下为已接收内容。\n\n${message.content}` : message.content
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `project-${projectId}-report-${message.id}${isMock ? '-mock' : ''}${partial ? '-partial' : ''}.md`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return <>
    <header className="page-heading">
      <div>
        <p className="eyebrow">筑衡 · 智能体决策解释</p>
        <h1>对话与报告</h1>
        <p className="muted">围绕当前方案追问依据、预览参数调整，或生成可追溯的比选报告。</p>
      </div>
      <div className="action-row">
        <Tag>{isMock ? '本地 Mock 演示' : '真实接口'}</Tag>
        <Button onClick={() => void start('report')} disabled={!canStart}>
          <IconFileText size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          生成 Markdown 报告
        </Button>
      </div>
    </header>
    {isMock && <Alert showIcon type="info" message="本地 Mock 演示：回答与工具卡均为确定性演示"
      description="文字使用已返回的演示评分。What-if 仅作流程示意，不计算调整后结果，不修改方案。" />}
    <div className="action-row" style={{ marginBottom: 16 }}>
      <Tag aria-label="当前决策视角">{decisionLabel(context)}</Tag>
      <span>{results.find(item => item.scheme_id === schemeId)?.scheme_name ?? '正在读取方案'}</span>
      <span className="muted">解释、报告与推演沿用此上下文。自定义权重顺序：居住品质 / 结构安全 / 施工友好 / 绿色低碳。</span>
    </div>
    <div className="chat-layout">
      <section className="chat-main panel" aria-label="方案对话">
        <div className="section-heading">
          <div>
            <h2>对话追问与解释</h2>
            <p className="section-subtext">根据当前项目与所选方案建议追问，默认简洁回答</p>
          </div>
          <span className="muted" role="status">{planning ? '正在理解调整要求…' : busy ? '正在生成…' : pendingPlan ? '请确认调整参数' : '可追问 · 可溯源'}</span>
        </div>
        <div className="action-row" aria-label="快捷问题">
          {suggestionQuery.data?.questions.map((question) => <Button key={question} disabled={!canStart}
            style={{ maxWidth: '100%', whiteSpace: 'normal', height: 'auto', textAlign: 'left' }}
            onClick={() => void prepare(question)}>{question}</Button>)}
          <Button type="text" size="small" loading={suggestionQuery.isFetching}
            disabled={busy || planning || !!pendingPlan || suggestionQuery.isFetching || evaluationQuery.isPending || rankingQuery.isPending}
            onClick={() => { freshSuggestions.current = true; void suggestionQuery.refetch() }}>刷新建议</Button>
        </div>
        <p className="muted" role="status">{suggestionQuery.isFetching ? '正在结合项目生成建议…'
          : suggestionQuery.isError ? suggestionQuery.error instanceof ApiError && suggestionQuery.error.status === 503
            ? suggestionQuery.error.message : '建议暂未生成，可刷新重试或直接输入追问。'
          : suggestionQuery.data?.source === 'fake' ? '项目情境建议 · 确定性演示'
          : suggestionQuery.data ? 'AI 建议 · 基于当前项目和所选方案' : ''}</p>
        <div className="chat-feed" ref={feed} role="log" aria-label="对话记录" aria-live="off"
          onScroll={() => { const node = feed.current; if (node) followStream.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80 }}>
          {!messages.length && <div className="chat-empty"><strong>从当前方案开始讨论</strong><p>选择上方建议问题，或输入想核对的依据与调整假设。比选报告也可以从右上角生成。</p></div>}
          {messages.map((item) => <article key={item.id} className={`chat-message ${item.role}`} data-role={item.role}>
            <div className="section-heading">
              <strong>{item.role === 'user' ? '你' : isMock ? '筑衡 · Mock 演示' : '筑衡 · 决策智能体'}</strong>
              {item.role === 'assistant' && <Tag>{item.status === 'streaming' ? '生成中' : item.status === 'done' ? '已完成' : item.status === 'cancelled' ? '已停止 · 内容未完成' : '生成失败 · 内容未完成'}</Tag>}
            </div>
            {item.decisionLabel && <Tag>{item.decisionLabel}</Tag>}
            {!!item.tools.length && <Collapse size="small" items={item.tools.map((tool) => ({ key: tool.id,
              label: `${({ get_result: '读取评估结果', search_clause: '查找参考依据', explain_metric: '查看判断依据', evaluate: '评估方案', rank: '比较方案', update_scheme_param: '创建推演方案' } as Record<string, string>)[tool.name] ?? '处理请求'} · ${tool.status === 'running' ? '处理中…' : tool.status === 'done' ? '已完成' : '未完成'}`,
              children: <pre>{tool.result === undefined ? (tool.status === 'running' ? '等待工具返回结果…' : '工具未返回详情') : toolResultText(tool.result)}</pre>,
            }))} />}
            {item.citationWarning && <Alert type="warning" showIcon message={item.status === 'done'
              ? '部分数字尚未通过来源校验，已标红，请核对依据。' : '当前草稿正在重新核对数字来源。'} />}
            {item.cached && <Tag>已读取报告缓存</Tag>}
            {item.role === 'user' ? <p>{item.content}</p> : item.unverifiedNumbers.length
              ? <div style={{ whiteSpace: 'pre-wrap' }}>{numberSegments(item.content, item.unverifiedNumbers)
                .map((segment, index) => segment.unverified
                  ? <mark key={index} style={{ color: '#b42318', background: '#fee4e2' }} title="数字尚未通过工具来源校验">{segment.text}</mark>
                  : segment.text)}</div> : <Markdown skipHtml
              remarkPlugins={[[remarkRuleLinks, { evaluations: results, preferredSchemeId: item.schemeId, knownRuleIds }]]}
              components={{ a: ({ href, children }) => {
                const match = href?.match(/^#trace\/([^/]*)\/([A-Z][A-Z0-9]*-\d{2,})$/)
                const owner = match && results.find((result) => encodeURIComponent(result.scheme_id) === match[1])
                // 未知规则或无效的内部链接只保留文字，不打开其他方案的抽屉。
                if (href?.startsWith('#trace/') && (!match || !knownRuleIds.has(match[2]) || (match[1] && !owner))) return <>{children}</>
                // 比较编码后的 ID，避免直接解码不可信的 Markdown 地址。
                if (match) return <Button type="link" size="small" aria-label={`查看规则 ${match[2]} 的依据`}
                  onClick={() => openTrace(match[2], owner?.scheme_id)}>{children}</Button>
                return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
              } }}>{item.content}</Markdown>}
            {item.status === 'streaming' && !item.content && <p className="muted">正在等待内容…</p>}
            {item.error && <Alert showIcon type="error" message="生成失败" description={item.error} />}
            {item.retryPreview && <div className="action-row">
              <span className="muted">当前数据已发生变化，需要重新查看参数预览并确认。</span>
              <Button disabled={!canStart} onClick={() => void prepare(item.retryPreview!.message, item.retryPreview!.change)}>重新预览调整</Button>
            </div>}
            {item.role === 'assistant' && item.kind === 'report' && item.content && item.status !== 'streaming'
              && <Button onClick={() => downloadReport(item)}>{item.status === 'done' ? '下载 Markdown（.md）' : '下载已接收部分（未完成 .md）'}</Button>}
          </article>)}
        </div>
        {planError && <Alert showIcon type="error" message="请求未执行" description={planError} />}
        {pendingPlan?.response.proposal && <section ref={preview} className="panel" aria-label="推演确认" style={{ margin: '16px 0' }}>
          <h3>确认这次参数调整</h3>
          <p><strong>{pendingPlan.response.proposal.scheme_name}</strong> · {decisionLabel(context)}</p>
          <table aria-label="调整参数预览" style={{ width: '100%', textAlign: 'left', marginBottom: 12 }}>
            <thead><tr><th>字段</th><th>原值</th><th>新值</th></tr></thead>
            <tbody><tr><td>{pendingPlan.response.proposal.field_label}</td>
              <td>{previewValue(pendingPlan.response.proposal.before)}</td>
              <td>{previewValue(pendingPlan.response.proposal.after)}</td></tr></tbody>
          </table>
          <p className="muted">确认后创建独立推演副本，重新计算规则、指标与排名。原方案保持不变。</p>
          <div className="action-row">
            <Button onClick={() => {
              setInput(pendingPlan.request.message ?? '')
              pendingRef.current = false
              setPendingPlan(undefined)
            }}>返回修改</Button>
            <Button type="primary" onClick={() => {
              if (!pendingRef.current || active.current) return
              const request = pendingPlan.request
              pendingRef.current = false
              setPendingPlan(undefined)
              void start('chat', request.message ?? '', undefined, request)
            }}>确认创建副本并推演</Button>
          </div>
        </section>}
        <form className="chat-compose" onSubmit={(event) => { event.preventDefault(); void prepare() }}>
          <Input.TextArea aria-label="输入追问" placeholder="可以追问依据，也可以说：将当前方案的标准层重复率改为 0.85"
            maxLength={30_000}
            disabled={!!pendingPlan}
            value={input} onChange={(event) => setInput(event.target.value)} autoSize={{ minRows: 3, maxRows: 7 }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) {
                event.preventDefault(); void prepare()
              }
            }} />
          <div className="action-row"><span className="muted">Enter 发送 · Shift + Enter 换行</span>
            {(busy || planning) && <Button onClick={cancel}>{planning ? '停止解析' : '停止生成'}</Button>}
            <Button type="primary" htmlType="submit" disabled={!canStart || !input.trim()}>发送</Button></div>
        </form>
      </section>
      <aside className="chat-side" aria-label="评估与排序摘要">
        <section className="panel">
          <div className="section-heading"><h2 style={{ whiteSpace: 'nowrap' }}>排名速览</h2><Tag>{context.role === 'custom' ? '自定义权重' : decisionLabel(context)}</Tag></div>
          {rankingQuery.isPending && <Skeleton active paragraph={{ rows: 3 }} />}
          {rankingQuery.isError && <Alert type="error" message="排序加载失败" description={rankingQuery.error.message}
            action={<Button size="small" onClick={() => void rankingQuery.refetch()}>重试</Button>} />}
          {rankingQuery.isSuccess && !ranks.length && <Empty description="暂无可展示的排序结果" />}
          {ranks.map((row) => <div key={row.scheme_id}>
            <div className="section-heading"><span>#{row.rank} {row.scheme_name}</span><strong>{displayNumber(row.closeness, 4)}</strong></div>
            <Progress percent={Math.max(0, Math.min(100, row.closeness * 100))} showInfo={false} size="small" />
          </div>)}
          <p className="muted">当前视角下正式方案的排序；本次推演副本与原方案的比较见正文。</p>
          <Link to={`/projects/${encodeURIComponent(projectId)}/dashboard`}
            onClick={() => updateContext({ schemeId })}>查看完整比选看板</Link>
        </section>
        <section className="panel">
          <div className="section-heading"><h2>追问与溯源方案</h2></div>
          {evaluationQuery.isPending && <Skeleton active paragraph={{ rows: 2 }} />}
          {evaluationQuery.isError && <Alert type="error" message="评估加载失败" description={evaluationQuery.error.message}
            action={<Button size="small" onClick={() => void evaluationQuery.refetch()}>重试</Button>} />}
          {evaluationQuery.isSuccess && !results.length && <Empty description="暂无评估结果，请先评估方案" />}
          {!!results.length && <Select aria-label="选择追问与溯源方案" value={schemeId} disabled={busy || planning || !!pendingPlan}
            onChange={schemeId => updateContext({ schemeId })} options={results.map((item) => ({ value: item.scheme_id, label: item.scheme_name || item.scheme_id }))} />}
          <p className="muted">正文明确提到方案时，优先追溯该方案；其余规则编号使用所选方案。</p>
          {!isMock && <>
          <p className="muted">假设调整标准层重复率（0–1），比较副本与原方案。</p>
          <div style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
          <InputNumber aria-label="假设的标准层重复率" min={0} max={1} step={0.01}
            value={whatifValue} onChange={setWhatifValue} disabled={busy || planning || !!pendingPlan} />
          <Button disabled={!canStart || !schemeId || whatifValue == null} onClick={() => {
            if (schemeId && whatifValue != null) void prepare(
              `假设将当前方案的标准层重复率改为 ${whatifValue}，比较修改前后的指标与排名。`,
              { scheme_id: Number(schemeId), field: 'std_floor_repeat', value: whatifValue })
          }}>预览参数调整</Button>
          </div>
          </>}
          <Link to={`/projects/${encodeURIComponent(projectId)}/schemes`}>前往方案管理</Link>
        </section>
        <section className="panel">
          <h2>规则依据</h2>
          {rulesQuery.isPending && <Skeleton active paragraph={{ rows: 1 }} />}
          {rulesQuery.isError && <Alert type="error" message="规则目录加载失败" description={rulesQuery.error.message}
            action={<Button size="small" onClick={() => void rulesQuery.refetch()}>重试</Button>} />}
          {rulesQuery.data && <p className="muted">已返回 {rulesQuery.data.rules.length} 条规则；
            {rulesQuery.data.todo_source_ids.length} 条出处待确认。点击正文编号查看计算与来源。</p>}
        </section>
      </aside>
    </div>
    <TraceDrawer evaluation={currentEvaluation} dimension={trace?.dimension} ruleId={trace?.ruleId}
      open={!!trace} onClose={() => setTrace(undefined)} />
  </>
}
