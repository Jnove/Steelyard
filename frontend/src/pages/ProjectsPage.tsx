import { useState } from 'react'
import { Button, Empty, Modal, Skeleton, Space, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { projects } from '../api/projects'
import { schema } from '../api/schema'
import type { Project, ProjectParams } from '../api/types'
import SchemaForm, { RequestErrors } from '../components/SchemaForm'
import type { SchemaFormValues } from '../components/SchemaForm'

function displayDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [messageApi, messageContext] = message.useMessage()
  const projectQuery = useQuery({ queryKey: ['projects'], queryFn: () => projects.list() })
  const schemaQuery = useQuery({ queryKey: ['schema'], queryFn: () => schema.get() })
  const createProject = useMutation({
    mutationFn: (values: SchemaFormValues) => projects.create({ name: values.name, params: values.params as ProjectParams }),
    onSuccess: async (project) => {
      queryClient.setQueryData(['project', project.id], project)
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
      setOpen(false)
      void messageApi.success('项目已创建，接下来添加候选方案。')
      navigate(`/projects/${project.id}/schemes`)
    },
  })
  const columns: ColumnsType<Project> = [
    { title: '项目名称', dataIndex: 'name', key: 'name', render: (_, project) => <Link to={`/projects/${project.id}/schemes`}>{project.name}</Link> },
    { title: '用地面积', key: 'site_area', render: (_, project) => project.params.site_area == null ? <Typography.Text type="secondary">—</Typography.Text> : `${project.params.site_area.toLocaleString('zh-CN')} m²` },
    { title: '气候分区', key: 'climate_zone', render: (_, project) => project.params.climate_zone || <Typography.Text type="secondary">—</Typography.Text> },
    { title: '最近更新', dataIndex: 'updated_at', key: 'updated_at', render: (value: string) => <span className="muted">{displayDate(value)}</span>, sorter: (left, right) => Date.parse(left.updated_at) - Date.parse(right.updated_at), defaultSortOrder: 'descend' },
    { title: '操作', key: 'actions', render: (_, project) => <Space><Link to={`/projects/${project.id}/schemes`}>管理方案</Link><Link to={`/projects/${project.id}/dashboard`}>查看评估</Link></Space> },
  ]
  const openCreate = () => { createProject.reset(); setOpen(true) }

  return (
    <>
      {messageContext}
      <header className="page-heading">
        <div>
          <p className="eyebrow">筑衡 · 项目工作台</p>
          <h1>从一个地块，走向更好的建筑决策。</h1>
          <p className="page-description">整理地块条件，汇集候选方案，在同一尺度下比较建筑品质、建造成本与绿色表现。</p>
        </div>
        <Button type="primary" size="large" onClick={openCreate}>新建项目</Button>
      </header>
      <section className="panel" aria-labelledby="projects-title">
        <div className="section-heading"><h2 id="projects-title">我的项目</h2><span className="muted">{projectQuery.data ? `共 ${projectQuery.data.length} 个项目` : '地块与方案的统一入口'}</span></div>
        {projectQuery.isError && <><RequestErrors error={projectQuery.error} title="项目列表加载失败" /><Button onClick={() => void projectQuery.refetch()} loading={projectQuery.isFetching}>重新加载</Button></>}
        {projectQuery.isPending ? <Skeleton active paragraph={{ rows: 5 }} /> : projectQuery.data && (
          <Table<Project>
            rowKey="id"
            columns={columns}
            dataSource={projectQuery.data}
            loading={projectQuery.isFetching}
            scroll={{ x: 800 }}
            pagination={{ pageSize: 10, hideOnSinglePage: true, showSizeChanger: false }}
            locale={{ emptyText: <Empty description="还没有项目，从录入第一个地块开始。"><Button type="primary" onClick={openCreate}>新建项目</Button></Empty>, triggerAsc: '按时间升序', triggerDesc: '按时间降序', cancelSort: '取消排序' }}
          />
        )}
      </section>
      <Modal title="新建项目" open={open} footer={null} width={800} maskClosable={false} closable={!createProject.isPending} keyboard={!createProject.isPending} onCancel={() => { if (!createProject.isPending) setOpen(false) }}>
        {open && (schemaQuery.isPending ? <Skeleton active /> : schemaQuery.data ? <SchemaForm schema={schemaQuery.data.project_params} nameLabel="项目名称" pending={createProject.isPending} error={createProject.error} onSubmit={(values) => createProject.mutate(values)} onCancel={() => setOpen(false)} /> : <><RequestErrors error={schemaQuery.error} title="项目参数加载失败" /><Button loading={schemaQuery.isFetching} onClick={() => void schemaQuery.refetch()}>重新加载</Button></>)}
      </Modal>
    </>
  )
}
