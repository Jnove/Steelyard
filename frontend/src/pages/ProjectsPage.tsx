import { useState } from 'react'
import { Button, Empty, Modal, Skeleton, Space, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { projects } from '../api/projects'
import { schema } from '../api/schema'
import type { Project, ProjectParams } from '../api/types'
import SchemaForm, { RequestErrors } from '../components/SchemaForm'
import type { SchemaFormValues } from '../components/SchemaForm'
import {
  IconArrowRight,
  IconAward,
  IconHardHat,
  IconHome,
  IconShieldCheck,
  IconSliders,
} from '../components/Icons'

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

  // 标杆示例项目优先展示
  const featured = projectQuery.data?.find(p => p.id === 1) ?? projectQuery.data?.[0]

  return (
    <>
      {messageContext}

      {/* 大赛主题与系统定位 Hero */}
      <header className="page-heading hero-heading">
        <div>
          <div className="hero-kicker">
            <span className="hero-tag">海之子杯 · 智能设计与方案优化</span>
            <span className="hero-theme-note">为人民建好房 · 为工友谋幸福</span>
          </div>
          <h1>筑衡 · 面向“好房子”建设的建筑方案智能比选系统</h1>
          <p className="page-description">
            在方案设计阶段，对多套候选住宅方案依次进行规范合规初筛、四维量化评估与多准则比选。数值由确定性引擎计算，大模型负责需求理解与决策溯源。
          </p>
        </div>
        <Button type="primary" size="large" onClick={openCreate}>新建项目</Button>
      </header>

      {/* 标杆案例一键体验看板 (首届海之子杯基准案例) */}
      {featured && (
        <section className="panel featured-case-panel" aria-labelledby="featured-title">
          <div className="featured-case-header">
            <div>
              <div className="featured-badge">
                <IconAward size={16} />
                <span>评审推荐体验 · 标杆主案例</span>
              </div>
              <h2 id="featured-title">{featured.name}</h2>
              <p className="featured-desc">
                以杭州钱塘保障房为地块原型，涵盖高品质剪力墙、违规方案、MiC高标准化、现浇框剪与被支配方案等 5 套代表性方案，全流程展现权衡、合规与推演。
              </p>
            </div>
            <div className="featured-actions">
              <Link to={`/projects/${featured.id}/dashboard`}>
                <Button type="primary" size="large" className="cta-button">
                  体验示例比选看板 <IconArrowRight size={16} style={{ marginLeft: 6, verticalAlign: 'middle' }} />
                </Button>
              </Link>
              <Link to={`/projects/${featured.id}/schemes`}>
                <Button size="large">方案参数对照</Button>
              </Link>
              <Link to={`/projects/${featured.id}/chat`}>
                <Button size="large">追问与报告</Button>
              </Link>
            </div>
          </div>

          <div className="featured-highlights-grid">
            <div className="highlight-item">
              <div className="highlight-icon" style={{ color: 'var(--color-primary)' }}>
                <IconHome size={20} />
              </div>
              <div>
                <strong>建好房 · 居住品质量化</strong>
                <p>把关 3.0m+ 舒适层高、南向采光比例与套内得房率，杜绝公摊刺客与暗间缺陷。</p>
              </div>
            </div>
            <div className="highlight-item">
              <div className="highlight-icon" style={{ color: 'var(--dimension-construction)' }}>
                <IconHardHat size={20} />
              </div>
              <div>
                <strong>谋幸福 · 工友安全前置</strong>
                <p>将工友安全前置到方案图纸，量化标准层重复率与预估装配率，规避高空危大工程。</p>
              </div>
            </div>
            <div className="highlight-item">
              <div className="highlight-icon" style={{ color: 'var(--dimension-green)' }}>
                <IconShieldCheck size={20} />
              </div>
              <div>
                <strong>防幻觉 · 双引擎可信决策</strong>
                <p>确定性引擎负责精确计算，大模型专注意图理解与结论解释，每项结论均可溯源。</p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* 系统四大价值支柱 */}
      <section className="pillars-grid" aria-label="核心价值">
        <div className="pillar-card">
          <div className="pillar-header">
            <IconHome size={20} style={{ color: 'var(--color-primary)' }} />
            <h3>居住品质前置化</h3>
          </div>
          <p>对标国家“好房子”建设标准，综合量化采光朝向、套内得房率与室内净高，在设计初期保障百姓居住舒适度。</p>
          <div className="pillar-tag-row">
            <Tag>3.0m+ 层高</Tag>
            <Tag>南向房间比</Tag>
            <Tag>得房率</Tag>
          </div>
        </div>

        <div className="pillar-card">
          <div className="pillar-header">
            <IconHardHat size={20} style={{ color: 'var(--dimension-construction)' }} />
            <h3>施工友好与工友安全</h3>
          </div>
          <p>落实“设计防范 (PtD)”理念，量化标准层重复率、构件种类数与装配率，大幅降低现场高空与湿作业隐患。</p>
          <div className="pillar-tag-row">
            <Tag>MiC 模块化</Tag>
            <Tag>标准层重复</Tag>
            <Tag>危大工程规避</Tag>
          </div>
        </div>

        <div className="pillar-card">
          <div className="pillar-header">
            <IconShieldCheck size={20} style={{ color: 'var(--color-success)' }} />
            <h3>可信双引擎防幻觉</h3>
          </div>
          <p>将大模型与确定性规则计算彻底解耦。合规判定与 MCDM 排序全部由本地算法输出，拒绝大模型工程数值幻觉。</p>
          <div className="pillar-tag-row">
            <Tag>确定性规则</Tag>
            <Tag>条文溯源</Tag>
            <Tag>引用核验</Tag>
          </div>
        </div>

        <div className="pillar-card">
          <div className="pillar-header">
            <IconSliders size={20} style={{ color: 'var(--dimension-structure)' }} />
            <h3>多准则动态权衡与推演</h3>
          </div>
          <p>内置政府保障房、施工总包、开发企业、业主住户四套决策矩阵。支持自然语言 What-if 参数假设与敏感性分析。</p>
          <div className="pillar-tag-row">
            <Tag>AHP + TOPSIS</Tag>
            <Tag>敏感性分析</Tag>
            <Tag>What-if 推演</Tag>
          </div>
        </div>
      </section>

      {/* 我的项目列表 */}
      <section className="panel" aria-labelledby="projects-title">
        <div className="section-heading">
          <div>
            <h2 id="projects-title">我的项目</h2>
            <p className="section-subtext">整理地块规划指标，管理候选方案集合</p>
          </div>
          <span className="muted">{projectQuery.data ? `共 ${projectQuery.data.length} 个项目` : '地块与方案的统一入口'}</span>
        </div>
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
