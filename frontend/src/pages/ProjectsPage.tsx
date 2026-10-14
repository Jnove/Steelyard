import { useState } from 'react'
import { Button, Empty, Modal, Select, Skeleton, Space, Table, Tooltip, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { projects } from '../api/projects'
import { USE_MOCK } from '../api/client'
import { schemes } from '../api/schemes'
import { schema } from '../api/schema'
import type { Project, ProjectParams } from '../api/types'
import SchemaForm, { RequestErrors } from '../components/SchemaForm'
import type { SchemaFormValues } from '../components/SchemaForm'
import BuildingShowcase from '../components/BuildingShowcase'
import { IconArrowRight, IconPlus, IconScale, IconShieldCheck, IconMessage } from '../components/Icons'

function displayDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function isTeachingCase(project: Pick<Project, 'name'>): boolean {
  return project.name.includes('下沙公租房一期') && project.name.includes('教学')
}

export function featuredProject(items: Project[] = [], selectedId?: number): Project | undefined {
  return items.find(project => project.id === selectedId)
    ?? items.find(isTeachingCase) ?? items.find(project => project.name.includes('虚构')) ?? items[0]
}

export async function clearProjectDerivedQueries(queryClient: QueryClient, projectId: number): Promise<void> {
  // 取消在途请求，避免保存前的响应重新写回缓存；仅清理本项目的派生结果。
  const predicate = (query: { queryKey: readonly unknown[] }) =>
    ['evaluation', 'rank', 'agent', 'agent-results', 'report', 'chat'].includes(String(query.queryKey[0]))
    && Number(query.queryKey[1]) === projectId
  await queryClient.cancelQueries({ predicate })
  queryClient.removeQueries({ predicate })
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['projects'] }),
    queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
  ])
}

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [editingProject, setEditingProject] = useState<Project>()
  const [selectedProjectId, setSelectedProjectId] = useState<number>()
  const [messageApi, messageContext] = message.useMessage()
  const projectQuery = useQuery({ queryKey: ['projects'], queryFn: () => projects.list() })
  const schemaQuery = useQuery({ queryKey: ['schema'], queryFn: () => schema.get() })
  // 优先真实地块上的教学推演；编号和列表位置不决定方案真实性。
  const featured = featuredProject(projectQuery.data, selectedProjectId)
  const schemeQuery = useQuery({ queryKey: ['schemes', featured?.id], queryFn: () => schemes.list(featured!.id), enabled: !!featured })
  const fictional = Boolean(featured?.name.includes('虚构'))
  const teaching = !!featured && isTeachingCase(featured)
  const notes: unknown = featured ? Reflect.get(featured.params, 'project_notes') : undefined
  const projectNotes = typeof notes === 'string' ? notes : undefined
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
  const updateProject = useMutation({
    mutationFn: ({ id, values }: { id: number; values: SchemaFormValues }) =>
      projects.update(id, { name: values.name, params: values.params as ProjectParams }),
    onSuccess: async (project) => {
      queryClient.setQueryData(['project', project.id], project)
      await clearProjectDerivedQueries(queryClient, project.id)
      setOpen(false)
      setEditingProject(undefined)
      void messageApi.success('地块已更新，请重新评估候选方案后查看比选结果。')
    },
  })
  const pending = createProject.isPending || updateProject.isPending
  const openEdit = (project: Project) => {
    if (USE_MOCK) return
    updateProject.reset(); createProject.reset(); setEditingProject(project); setOpen(true)
  }
  const columns: ColumnsType<Project> = [
    { title: '项目名称', dataIndex: 'name', key: 'name', render: (_, project) => <Link to={`/projects/${project.id}/schemes`}>{project.name}</Link> },
    { title: '用地面积', key: 'site_area', render: (_, project) => project.params.site_area == null ? <Typography.Text type="secondary">—</Typography.Text> : `${project.params.site_area.toLocaleString('zh-CN')} m²` },
    { title: '气候分区', key: 'climate_zone', render: (_, project) => project.params.climate_zone || <Typography.Text type="secondary">—</Typography.Text> },
    { title: '最近更新', dataIndex: 'updated_at', key: 'updated_at', render: (value: string) => <span className="muted">{displayDate(value)}</span>, sorter: (left, right) => Date.parse(left.updated_at) - Date.parse(right.updated_at), defaultSortOrder: 'descend' },
    { title: '操作', key: 'actions', render: (_, project) => <Space><Link to={`/projects/${project.id}/schemes`}>管理方案</Link><Link to={`/projects/${project.id}/dashboard`}>查看评估</Link><Tooltip title={USE_MOCK ? '离线快照不支持编辑地块或切换地区标准，请连接后端。' : '修改地块条件、来源说明和适用标准册；保存后需重新评估。'}><span><Button type="link" disabled={USE_MOCK} onClick={() => openEdit(project)}>编辑地块</Button></span></Tooltip></Space> },
  ]
  const openCreate = () => { createProject.reset(); updateProject.reset(); setEditingProject(undefined); setOpen(true) }
  return <>
    {messageContext}
    <section className="overview-hero" aria-labelledby="overview-title">
      <div className="hero-copy">
        <p className="hero-eyebrow"><span className="status-dot" />STEELYARD <span>建筑方案智能比选</span></p>
        <h1 id="overview-title">好房子，<br /><span>有据可选。</span></h1>
        <p className="hero-intro">在品质、结构、施工与绿色之间，找到值得讨论的选择。把方案放在同一尺度上比较，再沿着计算依据追问。</p>
        <div className="hero-actions">
          {featured && <Link to={`/projects/${featured.id}/dashboard`}><Button type="primary" size="large">{teaching ? '体验教学案例比选' : fictional ? '体验示例比选' : '打开比选看板'}<IconArrowRight size={17} /></Button></Link>}
          <Button size="large" className="hero-create" onClick={openCreate}><IconPlus size={17} />新建项目</Button>
        </div>
        <div className="hero-project glass-surface">
          <div className="hero-project-top"><span>{teaching ? '真实地块 · 教学方案' : fictional ? '虚构示例 · 流程体验' : featured ? '当前展示项目' : '你的项目工作空间'}</span><span>{schemeQuery.data ? `${schemeQuery.data.length} 个方案` : projectQuery.isPending ? '载入中' : '等待方案'}</span></div>
          {featured ? <>
            {(projectQuery.data?.length ?? 0) > 1 ? <Select aria-label="选择展台项目" value={featured.id} onChange={setSelectedProjectId} options={projectQuery.data?.map(p => ({ label: p.name, value: p.id }))} /> : <strong>{featured.name}</strong>}
            <div className="hero-project-links"><Link to={`/projects/${featured.id}/schemes`}>查看方案参数 <IconArrowRight size={13} /></Link><Link to={`/projects/${featured.id}/chat`}>追问与报告 <IconArrowRight size={13} /></Link></div>
          </> : <p>{projectQuery.isPending ? '正在整理项目…' : projectQuery.isError ? '项目暂未载入，可在下方重试。' : '从一块地、几种方案，开始一次有依据的比较。'}</p>}
          {fictional && <p className="hero-project-disclaimer">示例参数与规则用于流程演示，专业依据仍需核定。</p>}
          {teaching && <p className="hero-project-disclaimer">地块背景有公开来源；候选方案为教学推演，不代表建成项目的实际方案或质量评价。</p>}
          {projectNotes && <details className="hero-project-disclaimer"><summary>来源与适用边界</summary><p style={{ whiteSpace: 'pre-wrap' }}>{projectNotes}</p></details>}
        </div>
      </div>
      <BuildingShowcase key={featured?.id ?? 'empty'} schemes={schemeQuery.data ?? []} pending={!!featured && schemeQuery.isPending} failed={schemeQuery.isError} onRetry={() => void schemeQuery.refetch()} />
    </section>

    <section className="workflow-strip" aria-label="比选工作流程">
      <div><span className="workflow-number">01</span><IconScale size={20} /><strong>把取舍放在同一尺度</strong><p>四维评分与角色权重，比较不同关注重点。</p></div>
      <div><span className="workflow-number">02</span><IconShieldCheck size={20} /><strong>让依据跟得上结论</strong><p>从得分下钻到参数、公式与规则来源。</p></div>
      <div><span className="workflow-number">03</span><IconMessage size={20} /><strong>把下一步问清楚</strong><p>追问、假设推演与报告，接着完成讨论。</p></div>
    </section>

    <section className="panel project-library" aria-labelledby="projects-title">
      <div className="section-heading"><div><p className="eyebrow">YOUR WORKSPACE</p><h2 id="projects-title">我的项目</h2><p className="section-subtext">从地块条件，到每一种候选方案。</p></div><span className="project-count">{projectQuery.data ? `${String(projectQuery.data.length).padStart(2, '0')} 个项目` : '地块与方案的统一入口'}</span></div>
      {projectQuery.isError && <><RequestErrors error={projectQuery.error} title="项目列表加载失败" /><Button onClick={() => void projectQuery.refetch()} loading={projectQuery.isFetching}>重新加载</Button></>}
      {projectQuery.isPending ? <Skeleton active paragraph={{ rows: 5 }} /> : projectQuery.data && <Table<Project> rowKey="id" columns={columns} dataSource={projectQuery.data} loading={projectQuery.isFetching} scroll={{ x: 800 }} pagination={{ pageSize: 10, hideOnSinglePage: true, showSizeChanger: false }} locale={{ emptyText: <Empty description="还没有项目，从录入第一个地块开始。"><Button type="primary" onClick={openCreate}>新建项目</Button></Empty>, triggerAsc: '按时间升序', triggerDesc: '按时间降序', cancelSort: '取消排序' }} />}
    </section>
    <Modal title={editingProject ? '编辑地块' : '新建项目'} open={open} footer={null} width={800} maskClosable={false} closable={!pending} keyboard={!pending} onCancel={() => { if (!pending) setOpen(false) }}>
      {open && (schemaQuery.isPending ? <Skeleton active /> : schemaQuery.data ? <SchemaForm key={editingProject?.id ?? 'create'} schema={schemaQuery.data.project_params} nameLabel="项目名称" initialValues={editingProject} pending={pending} error={editingProject ? updateProject.error : createProject.error} onSubmit={(values) => editingProject ? updateProject.mutate({ id: editingProject.id, values }) : createProject.mutate(values)} onCancel={() => setOpen(false)} /> : <><RequestErrors error={schemaQuery.error} title="项目参数加载失败" /><Button loading={schemaQuery.isFetching} onClick={() => void schemaQuery.refetch()}>重新加载</Button></>)}
    </Modal>
  </>
}
