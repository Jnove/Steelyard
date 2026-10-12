import { useState } from 'react'
import { Alert, Button, Empty, Modal, Result, Skeleton, Table, Tag, Tooltip, Typography, Upload, message } from 'antd'
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
import { IconPlay, IconPlus, IconUpload, IconAlertTriangle, IconCheck } from '../components/Icons'

function getSchemePersona(name: string): { title: string; color: string; desc: string } {
  if (name.includes('A') || name.includes('高品质')) {
    return { title: '品质旗舰', color: '#2563eb', desc: '大层高·高得房率·工友施工难度大' }
  }
  if (name.includes('B') || name.includes('不合规')) {
    return { title: '红线待改', color: '#dc2626', desc: '层高2.9m低于国家好房子硬性标准' }
  }
  if (name.includes('C') || name.includes('MiC')) {
    return { title: 'MiC 标杆', color: '#d97706', desc: '装配率75%·极致标准化·工友施工最安全' }
  }
  if (name.includes('D') || name.includes('均衡')) {
    return { title: '综合均衡', color: '#059669', desc: '常规现浇框剪·各项指标中规中矩' }
  }
  if (name.includes('E') || name.includes('被支配')) {
    return { title: '劣势方案', color: '#64748b', desc: '各维度均落后于主流方案·帕累托淘汰' }
  }
  return { title: '候选方案', color: 'var(--color-primary)', desc: '多准则方案比选对象' }
}

function getGroupTag(group?: string) {
  if (!group) return <Tag className="field-group-tag default">其他参数</Tag>
  if (group.includes('品质')) return <Tag className="field-group-tag quality">居住品质</Tag>
  if (group.includes('施工') || group.includes('安全')) return <Tag className="field-group-tag construction">施工与工友安全</Tag>
  if (group.includes('结构') || group.includes('造价')) return <Tag className="field-group-tag structure">结构与造价</Tag>
  if (group.includes('绿色') || group.includes('低碳')) return <Tag className="field-group-tag green">绿色低碳</Tag>
  return <Tag className="field-group-tag default">{group}</Tag>
}

function displayValue(value: unknown, fieldName?: string) {
  if (value == null || value === '' || (Array.isArray(value) && !value.length) || (typeof value === 'object' && !Object.keys(value).length)) {
    return <Typography.Text type="secondary" aria-label="未填写">—</Typography.Text>
  }
  if (fieldName === 'floor_height' && typeof value === 'number') {
    if (value < 3.0) {
      return (
        <span className="spec-val-danger">
          <IconAlertTriangle size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
          {value.toFixed(1)} m (低于3.0m标准)
        </span>
      )
    }
    return <span className="spec-val-good">{value.toFixed(1)} m</span>
  }
  if (fieldName === 'prefab_ratio_est' && typeof value === 'number') {
    if (value >= 0.7) {
      return (
        <span className="spec-val-success">
          <IconCheck size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
          {(value * 100).toFixed(0)}% (MiC极高装配)
        </span>
      )
    }
    return `${(value * 100).toFixed(0)}%`
  }
  if (fieldName === 'std_floor_repeat' && typeof value === 'number') {
    if (value >= 0.9) {
      return <span className="spec-val-success">{(value * 100).toFixed(0)}% (极高重复率)</span>
    }
    return `${(value * 100).toFixed(0)}%`
  }
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
    {
      title: '参数 / 单位',
      key: 'field',
      fixed: 'left',
      width: 240,
      render: (_, field) => (
        <div className="spec-field-col">
          <div className="spec-field-name">
            <strong>{field.label}</strong>
            {field.description && (
              <Tooltip title={field.description}>
                <span tabIndex={0} aria-label={`${field.label}说明`} className="field-info-icon">ⓘ</span>
              </Tooltip>
            )}
          </div>
          <div className="spec-field-meta">
            {getGroupTag(field.group)}
            {field.unit && field.unit !== '—' && <span className="spec-unit">{field.unit}</span>}
          </div>
        </div>
      ),
    },
    ...(schemeQuery.data ?? []).map((scheme) => {
      const persona = getSchemePersona(scheme.name)
      return {
        title: () => (
          <div className="scheme-col-header" style={{ borderTopColor: persona.color }}>
            <strong>{scheme.name}</strong>
            <span className="persona-micro-tag" style={{ color: persona.color, borderColor: persona.color }}>{persona.title}</span>
          </div>
        ),
        key: scheme.id,
        width: 210,
        render: (_: unknown, field: FieldMetadata) => displayValue(Reflect.get(scheme.params, field.name), field.name),
      }
    }),
  ]

  const schemeColumns: ColumnsType<Scheme> = [
    {
      title: '方案名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => {
        const persona = getSchemePersona(name)
        return (
          <div className="scheme-name-cell">
            <strong style={{ color: persona.color }}>{name}</strong>
            <Tag color={name.includes('B') ? 'error' : name.includes('C') ? 'gold' : 'blue'}>{persona.title}</Tag>
          </div>
        )
      },
    },
    { title: '结构体系', key: 'structure_type', render: (_, scheme) => displayValue(scheme.params.structure_type) },
    {
      title: '已录入参数',
      key: 'completeness',
      render: (_, scheme) => {
        const count = rows.filter((field) => {
          const value: unknown = Reflect.get(scheme.params, field.name)
          return value != null && value !== '' && (typeof value !== 'object' || Object.keys(value).length > 0)
        }).length
        return schemaQuery.data ? <Tag color="cyan">{count} / {rows.length} 项完整</Tag> : <Typography.Text type="secondary">—</Typography.Text>
      },
    },
    { title: '操作', key: 'actions', render: (_, scheme) => <Button disabled={!canEdit} onClick={() => openEditor(scheme)} aria-label={`编辑${scheme.name}`}>编辑参数</Button> },
  ]

  return (
    <>
      {messageContext}
      <header className="page-heading">
        <div>
          <p className="eyebrow"><Link to="/projects">项目工作台</Link> / 方案参数录入与比选</p>
          <h1>{projectQuery.data?.name ?? (projectQuery.isPending ? '正在加载项目…' : '方案管理')}</h1>
          <p className="page-description">录入或批量导入候选方案，直观对照建筑品质、施工安全与绿色低碳设计参数，一键启动多准则综合评估。</p>
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
          >
            <Button loading={importSchemes.isPending} disabled={!projectQuery.data || busy}>
              <IconUpload size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />
              导入 Excel
            </Button>
          </Upload>
          <Button disabled={!canEdit} onClick={() => openEditor('new')}>
            <IconPlus size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            添加方案
          </Button>
          <Button
            type="primary"
            size="large"
            className="evaluate-cta-btn"
            loading={evaluate.isPending}
            disabled={!projectQuery.data || !schemeQuery.data?.length || schemeQuery.isError || busy}
            onClick={() => evaluate.mutate()}
          >
            <IconPlay size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            开始评估
          </Button>
        </div>
      </header>

      {projectQuery.isError && <><RequestErrors error={projectQuery.error} title="项目加载失败" /><Button loading={projectQuery.isFetching} onClick={() => void projectQuery.refetch()}>重试项目</Button></>}
      <RequestErrors error={fileError} title="无法导入文件" />
      <RequestErrors error={importSchemes.error} title="Excel 导入失败，请修正全部问题后重试" />
      {importSchemes.data && <><Alert showIcon type={importErrors.length ? 'warning' : 'success'} message={`已导入 ${importedCount} 个方案${importErrors.length ? `，另有 ${importErrors.length} 项问题需要处理` : ''}`} description={importSchemes.data.project_params_updated ? '已同步导入文件中的项目参数。' : undefined} /><RequestErrors error={importErrors} title="导入问题明细" /></>}
      <RequestErrors error={evaluate.error} title="评估失败，请检查参数后重试" />

      {/* 方案速览卡片长廊 (Visual Schemes Gallery) */}
      {schemeQuery.data && schemeQuery.data.length > 0 && (
        <section className="panel schemes-gallery-section" aria-label="候选方案概览">
          <div className="section-heading">
            <div>
              <h2>候选方案画像一览</h2>
              <p className="section-subtext">5 套方案设计参数各有侧重，点击下方【开始评估】由确定性引擎计算四维得分与 TOPSIS 优选结果</p>
            </div>
            <span className="muted">共 {schemeQuery.data.length} 个候选方案</span>
          </div>
          <div className="schemes-gallery-grid">
            {schemeQuery.data.map((scheme) => {
              const persona = getSchemePersona(scheme.name)
              const p = scheme.params
              return (
                <div key={scheme.id} className="scheme-overview-card" style={{ borderTopColor: persona.color }}>
                  <div className="scheme-overview-header">
                    <div>
                      <span className="persona-tag" style={{ color: persona.color, background: `${persona.color}15` }}>{persona.title}</span>
                      <h4>{scheme.name}</h4>
                    </div>
                    <Button size="small" onClick={() => openEditor(scheme)}>编辑</Button>
                  </div>
                  <p className="scheme-overview-desc">{persona.desc}</p>
                  <div className="scheme-spec-pills">
                    <div className="spec-pill">
                      <span>结构</span>
                      <strong>{p.structure_type || '—'}</strong>
                    </div>
                    <div className={`spec-pill ${p.floor_height && p.floor_height < 3.0 ? 'danger-pill' : ''}`}>
                      <span>层高</span>
                      <strong>{p.floor_height ? `${p.floor_height}m` : '—'}</strong>
                    </div>
                    <div className="spec-pill">
                      <span>装配率</span>
                      <strong>{p.prefab_ratio_est != null ? `${(p.prefab_ratio_est * 100).toFixed(0)}%` : '—'}</strong>
                    </div>
                    <div className="spec-pill">
                      <span>得房率</span>
                      <strong>{p.inner_area_ratio != null ? `${(p.inner_area_ratio * 100).toFixed(0)}%` : '—'}</strong>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* 候选方案列表 */}
      <section className="panel" aria-labelledby="schemes-title">
        <div className="section-heading">
          <div>
            <h2 id="schemes-title">候选方案列表</h2>
            <p className="section-subtext">维护候选集合，支持单方案参数修改与 Excel 批量维护</p>
          </div>
          <span className="muted">{schemeQuery.data ? `共 ${schemeQuery.data.length} 个方案` : '录入、调整与比较'}</span>
        </div>
        {schemeQuery.isError && <><RequestErrors error={schemeQuery.error} title="方案列表加载失败" /><Button loading={schemeQuery.isFetching} onClick={() => void schemeQuery.refetch()}>重新加载</Button></>}
        {schemeQuery.isPending ? <Skeleton active paragraph={{ rows: 4 }} /> : schemeQuery.data && <Table<Scheme> rowKey="id" columns={schemeColumns} dataSource={schemeQuery.data} loading={schemeQuery.isFetching} scroll={{ x: 600 }} pagination={false} locale={{ emptyText: <Empty description="还没有候选方案。手动录入，或从 Excel 一次导入多个方案。"><Button type="primary" disabled={!canEdit} onClick={() => openEditor('new')}>添加第一个方案</Button></Empty> }} />}
      </section>

      {/* 参数对照表 */}
      <section className="panel" aria-labelledby="comparison-title">
        <div className="section-heading">
          <div>
            <h2 id="comparison-title">参数横向对照</h2>
            <p className="section-subtext">每列代表一个方案 · 颜色药丸标识优势指标与合规隐患项</p>
          </div>
          <span className="muted">同一尺度 · 精细对比</span>
        </div>
        {schemaQuery.isError && <><RequestErrors error={schemaQuery.error} title="参数定义加载失败" /><Button loading={schemaQuery.isFetching} onClick={() => void schemaQuery.refetch()}>重试参数加载</Button></>}
        {schemaQuery.isPending || schemeQuery.isPending ? <Skeleton active paragraph={{ rows: 6 }} /> : schemaQuery.data && (schemeQuery.data ? <Table<FieldMetadata> className="comparison-table styled-spec-table" rowKey="name" columns={comparisonColumns} dataSource={rows} pagination={false} size="middle" scroll={{ x: 240 + (schemeQuery.data?.length ?? 0) * 210 }} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="添加方案后，在这里逐项比较设计参数。" />)}
      </section>

      <Modal title={editing === 'new' ? '添加候选方案' : `编辑方案 · ${editing?.name ?? ''}`} open={editing !== null} footer={null} width={900} maskClosable={false} closable={!saveScheme.isPending} keyboard={!saveScheme.isPending} onCancel={() => { if (!saveScheme.isPending) setEditing(null) }}>
        {editing !== null && schemaQuery.data && <SchemaForm key={editing === 'new' ? 'new' : editing.id} schema={schemaQuery.data.scheme_params} nameLabel="方案名称" initialValues={editing === 'new' ? undefined : editing} pending={saveScheme.isPending} error={saveScheme.error} onSubmit={(values) => saveScheme.mutate({ values, schemeId: editing === 'new' ? undefined : editing.id })} onCancel={() => setEditing(null)} />}
      </Modal>
    </>
  )
}

