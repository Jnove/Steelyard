import { Card, Typography } from 'antd'
import { useParams } from 'react-router-dom'

export default function SchemesPage() {
  const { id = '' } = useParams<{ id: string }>()
  return (
    <Card title={`方案管理 · 项目 ${id}`}>
      <Typography.Paragraph type="secondary">
        T1 脚手架：后续在此录入方案字段、批量导入 Excel，并按方案触发 /api/evaluate。
      </Typography.Paragraph>
    </Card>
  )
}