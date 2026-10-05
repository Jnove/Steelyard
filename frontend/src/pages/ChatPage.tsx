import { Alert, Button, Card, Input, Space, Typography } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { streamAgent, type AgentOutput, type NumberIssue } from '../api/agents'

function highlightNumbers(text: string, issues: NumberIssue[]) {
  // Python 的位置按 Unicode 字符计数，Array.from 可避免 emoji 导致位置偏移。
  const characters = Array.from(text)
  const spans = []
  let cursor = 0
  for (const issue of [...issues].sort((a, b) => a.start - b.start)) {
    spans.push(characters.slice(cursor, issue.start).join(''))
    spans.push(<mark key={issue.start} style={{ color: '#b42318', background: '#fee4e2' }} title="数字尚未通过工具来源校验">{characters.slice(issue.start, issue.end).join('')}</mark>)
    cursor = issue.end
  }
  spans.push(characters.slice(cursor).join(''))
  return spans
}

export default function ChatPage() {
  const { id = '' } = useParams<{ id: string }>()
  const [message, setMessage] = useState('')
  const [report, setReport] = useState('')
  const [issues, setIssues] = useState<NumberIssue[]>([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [history, setHistory] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const active = useRef<AbortController>()
  useEffect(() => {
    setReport('')
    setIssues([])
    setHistory([])
    setStatus('')
    setError('')
    return () => active.current?.abort()
  }, [id])

  async function submit(kind: 'report' | 'chat') {
    const controller = new AbortController()
    active.current = controller
    setBusy(true)
    setError('')
    setReport('')
    setIssues([])
    const text = message.trim()
    try {
      await streamAgent(id, kind, kind === 'report' ? {} : { message: text, history }, (event) => {
        if (event.name === 'node_start') setStatus(`正在执行：${String(event.data.node)}`)
        if (event.name === 'token') {
          const token = String(event.data.text ?? '')
          setReport((previous) => event.data.replace ? token : previous + token)
          if (event.data.replace) setIssues([])
        }
        if (event.name === 'citation_warning') setStatus(event.data.exhausted ? '部分数字未通过校验' : '正在核对引用并重写报告')
        if (event.name === 'error') setError(String(event.data.message))
        if (event.name === 'done') {
          const output = event.data as unknown as AgentOutput
          setReport(output.report)
          setIssues(output.unverified_numbers)
          setStatus(output.cached ? '已读取缓存报告' : '已完成')
          setHistory((previous) => [...previous, { role: 'user', content: kind === 'report' ? '生成方案比选报告' : text }, { role: 'assistant', content: output.report }].slice(-40) as typeof history)
          if (kind === 'chat') setMessage('')
        }
      }, controller.signal)
    } catch (reason: unknown) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '请求失败')
    } finally {
      if (active.current === controller) setBusy(false)
    }
  }

  return (
    <Card title={`对话追问 · 项目 ${id}`}>
      <Typography.Paragraph type="secondary">
        生成报告后可追问规则、修改方案参数或调整权重。比例请使用小数，假设推演会创建副本。
      </Typography.Paragraph>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Button loading={busy} onClick={() => void submit('report')}>生成比选报告</Button>
        <Space.Compact style={{ width: '100%' }}>
          <Input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="例如：解释 K-01；方案 3 std_floor_repeat 改为 0.6；权重改成 [0.1,0.2,0.3,0.4]" disabled={busy} />
          <Button type="primary" disabled={busy || !message.trim()} onClick={() => void submit('chat')}>发送</Button>
        </Space.Compact>
        {busy && <Button onClick={() => { active.current?.abort(); setStatus('已停止接收') }}>停止</Button>}
        <Typography.Text type="secondary">{status}</Typography.Text>
        {error && <Alert type="error" message={error} />}
        {issues.length > 0 && <Alert type="warning" message="标红数字尚未通过工具来源校验，请核对后使用。" />}
        <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{highlightNumbers(report, issues)}</div>
      </Space>
    </Card>
  )
}
