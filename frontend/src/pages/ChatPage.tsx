import { Card, Input, Space, Typography } from 'antd'
import { useParams } from 'react-router-dom'

export default function ChatPage() {
  const { id = '' } = useParams<{ id: string }>()
  return (
    <Card title={`对话追问 · 项目 ${id}`}>
      <Typography.Paragraph type="secondary">
        T1 脚手架：后续接入智能体图，对话与报告走 SSE 流式输出。
      </Typography.Paragraph>
      <Space.Compact style={{ width: '100%' }}>
        <Input placeholder="T1 阶段尚未接入 LLM，输入框仅作占位" disabled />
      </Space.Compact>
    </Card>
  )
}