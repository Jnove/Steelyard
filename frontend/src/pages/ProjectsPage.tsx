import { useState } from 'react'
import { Button, Empty, Modal, Select, Skeleton, Space, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { projects } from '../api/projects'
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

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [selectedProjectId, setSelectedProjectId] = useState<number>()
  const [messageApi, messageContext] = message.useMessage()
  const projectQuery = useQuery({ queryKey: ['projects'], queryFn: () => projects.list() })
  const schemaQuery = useQuery({ queryKey: ['schema'], queryFn: () => schema.get() })
  // 优先明确标注为虚构的案例；编号和列表位置不决定项目真实性。
  const featured = projectQuery.data?.find(p => p.id === selectedProjectId)
    ?? projectQuery.data?.find(p => p.name.includes('虚构')) ?? projectQuery.data?.[0]
  const schemeQuery = useQuery({ queryKey: ['schemes', featured?.id], queryFn: () => schemes.list(featured!.id), enabled: !!featured })
  const fictional = Boolean(featured?.name.includes('虚构'))
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
  return <>
    {messageContext}
    <section className="overview-hero" aria-labelledby="overview-title">
      <div className="hero-copy">
        <p className="hero-eyebrow"><span className="status-dot" />STEELYARD <span>建筑方案智能比选</span></p>
        <h1 id="overview-title">好房子，<br /><span>有据可选。</span></h1>
        <p className="hero-intro">在品质、结构、施工与绿色之间，找到值得讨论的选择。把方案放在同一尺度上比较，再沿着计算依据追问。</p>
        <div className="hero-actions">
          {featured && <Link to={`/projects/${featured.id}/dashboard`}><Button type="primary" size="large">{fictional ? '体验示例比选' : '打开比选看板'}<IconArrowRight size={17} /></Button></Link>}
          <Button size="large" className="hero-create" onClick={openCreate}><IconPlus size={17} />新建项目</Button>
        </div>
        <div className="hero-project glass-surface">
          <div className="hero-project-top"><span>{fictional ? '虚构示例 · 流程体验' : featured ? '当前展示项目' : '你的项目工作空间'}</span><span>{schemeQuery.data ? `${schemeQuery.data.length} 个方案` : projectQuery.isPending ? '载入中' : '等待方案'}</span></div>
          {featured ? <>
            {(projectQuery.data?.length ?? 0) > 1 ? <Select aria-label="选择展台项目" value={featured.id} onChange={setSelectedProjectId} options={projectQuery.data?.map(p => ({ label: p.name, value: p.id }))} /> : <strong>{featured.name}</strong>}
            <div className="hero-project-links"><Link to={`/projects/${featured.id}/schemes`}>查看方案参数 <IconArrowRight size={13} /></Link><Link to={`/projects/${featured.id}/chat`}>追问与报告 <IconArrowRight size={13} /></Link></div>
          </> : <p>{projectQuery.isPending ? '正在整理项目…' : projectQuery.isError ? '项目暂未载入，可在下方重试。' : '从一块地、几种方案，开始一次有依据的比较。'}</p>}
          {fictional && <p className="hero-project-disclaimer">示例参数与规则用于流程演示，专业依据仍需核定。</p>}
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
    <Modal title="新建项目" open={open} footer={null} width={800} maskClosable={false} closable={!createProject.isPending} keyboard={!createProject.isPending} onCancel={() => { if (!createProject.isPending) setOpen(false) }}>
      {open && (schemaQuery.isPending ? <Skeleton active /> : schemaQuery.data ? <SchemaForm schema={schemaQuery.data.project_params} nameLabel="项目名称" pending={createProject.isPending} error={createProject.error} onSubmit={(values) => createProject.mutate(values)} onCancel={() => setOpen(false)} /> : <><RequestErrors error={schemaQuery.error} title="项目参数加载失败" /><Button loading={schemaQuery.isFetching} onClick={() => void schemaQuery.refetch()}>重新加载</Button></>)}
    </Modal>
  </>
}
