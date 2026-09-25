import { Card, Empty, Typography } from 'antd'

export default function ProjectsPage() {
  return (
    <Card title="项目列表">
      <Typography.Paragraph type="secondary">
        T1 脚手架：此处将列出所有项目（地块条件），并提供新建项目的入口。后续任务接入 SQLModel 与 /api/projects。
      </Typography.Paragraph>
      <Empty description="暂无项目" />
    </Card>
  )
}