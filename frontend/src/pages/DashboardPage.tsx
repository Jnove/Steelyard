import { Card, Typography } from 'antd'
import { useParams } from 'react-router-dom'

export default function DashboardPage() {
  const { id = '' } = useParams<{ id: string }>()
  return (
    <Card title={`比选看板 · 项目 ${id}`}>
      <Typography.Paragraph type="secondary">
        T1 脚手架：后续在此展示合规清单、四维雷达图、TOPSIS 排名与敏感性热力图。
      </Typography.Paragraph>
    </Card>
  )
}