import { useState } from 'react'
import { Alert, Button, Empty, Modal, Result, Skeleton, Space, Table, Tag, Tooltip, Typography, Upload, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { projects } from '../api/projects'
import { schemes } from '../api/schemes'
import { evaluation } from '../api/evaluation'
import { schema } from '../api/schema'
import type { FieldMetadata, Scheme, SchemeParams } from '../api/types'
import SchemaForm, { orderedFields, RequestErrors } from '../components/SchemaForm'
import type { SchemaFormValues } from '../components/SchemaForm'

function displayValue(value: unknown) {
  if (value == null || value === '' || (Array.isArray(value) && !value.length) || (typeof value === 'object' && !Object.keys(value).length)) return <Typography.Text type="secondary" aria-label="未填写">—</Typography.Text>
  if (Array.isArray(value)) return value.map(String).join('、')
  if (typeof value === 'object') return Object.entries(value).map(([key, item]) => `${key}：${String(item)}`).join('；')
  if (typeof value === 'boolean') return value ? '是' : '否'
  return typeof value === 'number' ? value.toLocaleString('zh-CN', { maximumFractionDigits: 8 }) : String(value)
}

export default function SchemesPage() {
  const { id } = useParams<{ id: string }>()
  const projectId = Number(id)
  if (!Number.isSafeInteger(projectId) || projectId <= 0) return <Result status="404" title="无效的项目编号" subTitle="请从项目列表选择一个有效项目。" extra={<Link to="/projects">返回项目列表</Link>} />
  return <ProjectSchemes key={projectId} projectId={projectId} />
}

function ProjectSchemes({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [messageApi, messageContext] = message.useMessage()
  const [editing, setEditing] = useState<Scheme | 'new' | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const projectQuery = useQuery({ queryKey: ['project', projectId], queryFn: () => projects.get(projectId) })
  const schemeQuery = useQuery({ queryKey: ['schemes', projectId], queryFn: () => schemes.list(projectId) })
  const schemaQuery = useQuery({ queryKey: ['schema'], queryFn: () => schema.get() })
  const invalidateResults = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['schemes', projectId] }),
      queryClient.invalidateQueries({ queryKey: ['evaluation', projectId] }),
      queryClient.invalidateQueries({ queryKey: ['rank', projectId] }),
    ])
  }
  const saveScheme = useMutation({
    mutationFn: ({ values, schemeId }: { values: SchemaFormValues; schemeId?: number }) => {
      const input = { name: values.name, params: values.params as SchemeParams }
      return schemeId === undefined ? schemes.create(projectId, input) : schemes.update(projectId, schemeId, input)
    },
    onSuccess: async () => {
      await invalidateResults()
      setEditing(null)
      void messageApi.success('方案已保存，可重新评估查看最新结果。')
    },
  })
  const importSchemes = useMutation({
    mutationFn: (file: File) => schemes.importExcel(projectId, file),
    onSuccess: async () => {
      await Promise.all([
        invalidateResults(),
        queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['projects'] }),
      ])
    },
  })
  const evaluate = useMutation({
    mutationFn: () => evaluation.run(projectId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['evaluation', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['rank', projectId] }),
      ])
      navigate(`/projects/${projectId}/dashboard`)
    },
  })
  const busy = saveScheme.isPending || importSchemes.isPending || evaluate.isPending
  const importedCount = importSchemes.data?.created?.length ?? 0
  const importErrors = importSchemes.data?.errors ?? []
  const canEdit = Boolean(projectQuery.data && schemaQuery.data && !busy)
  const openEditor = (scheme: Scheme | 'new') => { saveScheme.reset(); setEditing(scheme) }
  const rows = schemaQuery.data ? orderedFields(schemaQuery.data.scheme_params) : []
  const comparisonColumns: ColumnsType<FieldMetadata> = [
    { title: '参数 / 单位', key: 'field', fixed: 'left', width: 220, render: (_, field) => <><Space size={4}>{field.label}{field.description && <Tooltip title={field.description}><span tabIndex={0} aria-label={`${field.label}说明`}>ⓘ</span></Tooltip>}</Space><div className="muted">{field.group || '其他参数'}{field.unit && field.unit !== '—' ? ` · ${field.unit}` : ''}</div></> },
    ...(schemeQuery.data ?? []).map((scheme) => ({
      title: scheme.name,
      key: scheme.id,
      width: 200,
      render: (_: unknown, field: FieldMetadata) => displayValue(Reflect.get(scheme.params, field.name)),
    })),
  ]
  const schemeColumns: ColumnsType<Scheme> = [
    { title: '方案名称', dataIndex: 'name', key: 'name', render: (name: string) => <Typography.Text strong>{name}</Typography.Text> },
    { title: '结构体系', key: 'structure_type', render: (_, scheme) => displayValue(scheme.params.structure_type) },
    { title: '已录入参数', key: 'completeness', render: (_, scheme) => {
      const count = rows.filter((field) => {
        const value: unknown = Reflect.get(scheme.params, field.name)
        return value != null && value !== '' && (typeof value !== 'object' || Object.keys(value).length > 0)
      }).length
      return schemaQuery.data ? <Tag>{count} / {rows.length} 项</Tag> : <Typography.Text type="secondary">—</Typography.Text>
    } },
    { title: '操作', key: 'actions', render: (_, scheme) => <Button disabled={!canEdit} onClick={() => openEditor(scheme)} aria-label={`编辑${scheme.name}`}>编辑参数</Button> },
  ]

  return (
    <>
      {messageContext}
      <header className="page-heading">
        <div>
          <p className="eyebrow"><Link to="/projects">项目工作台</Link> / 方案管理</p>
          <h1>{projectQuery.data?.name ?? (projectQuery.isPending ? '正在加载项目…' : '方案管理')}</h1>
          <p className="page-description">为同一个地块探索不同可能。录入或导入候选方案，逐项比较参数，再生成综合评估。</p>
        </div>
        <div className="action-row">
          <Upload
            accept=".xlsx"
            showUploadList={false}
            disabled={!projectQuery.data || busy}
            beforeUpload={(file) => {
              setFileError(null)
              importSchemes.reset()
              if (!file.name.toLowerCase().endsWith('.xlsx')) setFileError('请选择 .xlsx 格式的 Excel 文件。')
              else if (file.size === 0) setFileError('所选文件为空，请选择包含方案参数的 Excel 文件。')
              else importSchemes.mutate(file)
              return false
            }}
          ><Button loading={importSchemes.isPending} disabled={!projectQuery.data || busy}>导入 Excel</Button></Upload>
          <Button disabled={!canEdit} onClick={() => openEditor('new')}>添加方案</Button>
          <Button type="primary" loading={evaluate.isPending} disabled={!projectQuery.data || !schemeQuery.data?.length || schemeQuery.isError || busy} onClick={() => evaluate.mutate()}>开始评估</Button>
        </div>
      </header>
      {projectQuery.isError && <><RequestErrors error={projectQuery.error} title="项目加载失败" /><Button loading={projectQuery.isFetching} onClick={() => void projectQuery.refetch()}>重试项目</Button></>}
      <RequestErrors error={fileError} title="无法导入文件" />
      <RequestErrors error={importSchemes.error} title="Excel 导入失败，请修正全部问题后重试" />
      {importSchemes.data && <><Alert showIcon type={importErrors.length ? 'warning' : 'success'} message={`已导入 ${importedCount} 个方案${importErrors.length ? `，另有 ${importErrors.length} 项问题需要处理` : ''}`} description={importSchemes.data.project_params_updated ? '已同步导入文件中的项目参数。' : undefined} /><RequestErrors error={importErrors} title="导入问题明细" /></>}
      <RequestErrors error={evaluate.error} title="评估失败，请检查参数后重试" />
      <section className="panel" aria-labelledby="schemes-title">
        <div className="section-heading"><h2 id="schemes-title">候选方案</h2><span className="muted">{schemeQuery.data ? `共 ${schemeQuery.data.length} 个方案` : '录入、调整与比较'}</span></div>
        {schemeQuery.isError && <><RequestErrors error={schemeQuery.error} title="方案列表加载失败" /><Button loading={schemeQuery.isFetching} onClick={() => void schemeQuery.refetch()}>重新加载</Button></>}
        {schemeQuery.isPending ? <Skeleton active paragraph={{ rows: 4 }} /> : schemeQuery.data && <Table<Scheme> rowKey="id" columns={schemeColumns} dataSource={schemeQuery.data} loading={schemeQuery.isFetching} scroll={{ x: 600 }} pagination={false} locale={{ emptyText: <Empty description="还没有候选方案。手动录入，或从 Excel 一次导入多个方案。"><Button type="primary" disabled={!canEdit} onClick={() => openEditor('new')}>添加第一个方案</Button></Empty> }} />}
      </section>
      <section className="panel" aria-labelledby="comparison-title">
        <div className="section-heading"><h2 id="comparison-title">参数对照</h2><span className="muted">每列一个方案 · 灰色横线表示未填写</span></div>
        {schemaQuery.isError && <><RequestErrors error={schemaQuery.error} title="参数定义加载失败" /><Button loading={schemaQuery.isFetching} onClick={() => void schemaQuery.refetch()}>重试参数加载</Button></>}
        {schemaQuery.isPending || schemeQuery.isPending ? <Skeleton active paragraph={{ rows: 6 }} /> : schemaQuery.data && schemeQuery.data && (schemeQuery.data.length ? <Table<FieldMetadata> className="comparison-table" rowKey="name" columns={comparisonColumns} dataSource={rows} pagination={false} size="middle" scroll={{ x: 220 + schemeQuery.data.length * 200 }} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="添加方案后，在这里逐项比较设计参数。" />)}
      </section>
      <Modal title={editing === 'new' ? '添加候选方案' : `编辑方案 · ${editing?.name ?? ''}`} open={editing !== null} footer={null} width={900} maskClosable={false} closable={!saveScheme.isPending} keyboard={!saveScheme.isPending} onCancel={() => { if (!saveScheme.isPending) setEditing(null) }}>
        {editing !== null && schemaQuery.data && <SchemaForm key={editing === 'new' ? 'new' : editing.id} schema={schemaQuery.data.scheme_params} nameLabel="方案名称" initialValues={editing === 'new' ? undefined : editing} pending={saveScheme.isPending} error={saveScheme.error} onSubmit={(values) => saveScheme.mutate({ values, schemeId: editing === 'new' ? undefined : editing.id })} onCancel={() => setEditing(null)} />}
      </Modal>
    </>
  )
}
