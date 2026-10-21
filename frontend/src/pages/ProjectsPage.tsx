import { useMemo, useRef, useState } from 'react'
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  ArrowUpDown,
  Box,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  Layers3,
  LoaderCircle,
  MapPin,
  MessageSquare,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { projects } from '../api/projects'
import { USE_MOCK } from '../api/client'
import { schemes } from '../api/schemes'
import { schema } from '../api/schema'
import type { Project, ProjectParams } from '../api/types'
import type { SchemaFormValues } from '../components/SchemaForm'
import BuildingShowcase from '../components/BuildingShowcase'
import ProjectForm, { HomeErrors } from '../components/home/ProjectForm'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../components/ui/dialog'
import { clearDeletedData } from '../utils/deletion-cache'

function displayDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
}

export function isTeachingCase(project: Pick<Project, 'name'>): boolean {
  return project.name.includes('教学') && !project.name.includes('虚构')
}

export function featuredProject(
  items: Project[] = [],
  selectedId?: number,
): Project | undefined {
  return (
    items.find((project) => project.id === selectedId) ??
    items.find(isTeachingCase) ??
    items.find((project) => project.name.includes('虚构')) ??
    items[0]
  )
}

export async function clearProjectDerivedQueries(
  queryClient: QueryClient,
  projectId: number,
): Promise<void> {
  // 取消在途请求，避免保存前的响应重新写回缓存；仅清理本项目的派生结果。
  const predicate = (query: { queryKey: readonly unknown[] }) =>
    [
      'evaluation',
      'rank',
      'agent',
      'agent-results',
      'report',
      'chat',
      'suggestions',
    ].includes(String(query.queryKey[0])) &&
    Number(query.queryKey[1]) === projectId
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
  const dialogOpener = useRef<HTMLElement | null>(null)
  const createButton = useRef<HTMLButtonElement>(null)
  const rememberOpener = () => {
    dialogOpener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
  }
  const restoreFocus = (event: Event) => {
    event.preventDefault()
    if (dialogOpener.current?.isConnected) dialogOpener.current.focus()
    else createButton.current?.focus()
  }
  const [editingProject, setEditingProject] = useState<Project>()
  const [deletingProject, setDeletingProject] = useState<Project>()
  const [selectedProjectId, setSelectedProjectId] = useState<number>()
  const [showVolume, setShowVolume] = useState(false)
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'updated_at', desc: true },
  ])
  const projectQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => projects.list(),
  })
  const schemaQuery = useQuery({
    queryKey: ['schema'],
    queryFn: () => schema.get(),
  })
  // 优先真实地块上的教学推演；编号和列表位置不决定方案真实性。
  const featured = featuredProject(projectQuery.data, selectedProjectId)
  const schemeQuery = useQuery({
    queryKey: ['schemes', featured?.id],
    queryFn: () => schemes.list(featured!.id),
    enabled: !!featured,
  })
  const fictional = Boolean(featured?.name.includes('虚构'))
  const teaching = !!featured && isTeachingCase(featured)
  const notes: unknown = featured
    ? Reflect.get(featured.params, 'project_notes')
    : undefined
  const projectNotes = typeof notes === 'string' ? notes : undefined
  const createProject = useMutation({
    mutationFn: (values: SchemaFormValues) =>
      projects.create({
        name: values.name,
        params: values.params as ProjectParams,
      }),
    onSuccess: async (project) => {
      queryClient.setQueryData(['project', project.id], project)
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
      setOpen(false)
      setNotice('项目已创建，接下来添加候选方案。')
      navigate(`/projects/${project.id}/schemes`)
    },
  })
  const updateProject = useMutation({
    mutationFn: ({ id, values }: { id: number; values: SchemaFormValues }) =>
      projects.update(id, {
        name: values.name,
        params: values.params as ProjectParams,
      }),
    onSuccess: async (project) => {
      queryClient.setQueryData(['project', project.id], project)
      await clearProjectDerivedQueries(queryClient, project.id)
      setOpen(false)
      setEditingProject(undefined)
      setNotice('地块已更新，请重新评估候选方案后查看比选结果。')
    },
  })
  const deleteProject = useMutation({
    mutationFn: (project: Project) => projects.remove(project.id),
    onSuccess: async (_, project) => {
      if (selectedProjectId === project.id) setSelectedProjectId(undefined)
      await clearDeletedData(queryClient, project.id)
      setDeletingProject(undefined)
      setNotice('项目及其方案已删除。')
    },
  })
  const pending =
    createProject.isPending ||
    updateProject.isPending ||
    deleteProject.isPending
  const openEdit = (project: Project) => {
    if (USE_MOCK) return
    rememberOpener()
    updateProject.reset()
    createProject.reset()
    setEditingProject(project)
    setOpen(true)
  }
  const openCreate = () => {
    rememberOpener()
    createProject.reset()
    updateProject.reset()
    setEditingProject(undefined)
    setOpen(true)
  }
  const data = useMemo(
    () =>
      (projectQuery.data ?? []).filter(
        (project) =>
          category === 'all' ||
          (category === 'teaching'
            ? isTeachingCase(project)
            : project.name.includes('虚构')),
      ),
    [projectQuery.data, category],
  )
  const columns: ColumnDef<Project>[] = [
    {
      accessorKey: 'name',
      header: '项目名称',
      cell: ({ row }) => (
        <div className="home-project-cell">
          <span
            className={`home-project-icon${row.original.id === featured?.id ? ' is-selected' : ''}`}
          >
            <FolderOpen size={19} strokeWidth={1.6} />
          </span>
          <div>
            <button
              className="home-project-name"
              onClick={() => setSelectedProjectId(row.original.id)}
              aria-pressed={row.original.id === featured?.id}
            >
              {row.original.name}
            </button>
            <span className="home-project-meta">
              {isTeachingCase(row.original)
                ? '教学方案'
                : row.original.name.includes('虚构')
                  ? '虚构示例'
                  : '项目地块'}
              <span>项目 {String(row.original.id).padStart(2, '0')}</span>
            </span>
          </div>
        </div>
      ),
    },
    {
      accessorFn: (project) => project.params.site_area,
      id: 'site_area',
      header: '用地面积',
      cell: ({ row }) => (
        <span className="home-area">
          {row.original.params.site_area == null ? (
            '未填写'
          ) : (
            <>
              {row.original.params.site_area.toLocaleString('zh-CN')}
              <small> m²</small>
            </>
          )}
        </span>
      ),
    },
    {
      accessorKey: 'updated_at',
      header: ({ column }) => (
        <button
          className="home-sort-header"
          onClick={column.getToggleSortingHandler()}
          aria-label="按更新时间排序"
        >
          最近更新
          {column.getIsSorted() === 'desc' ? (
            <ArrowDown size={12} />
          ) : column.getIsSorted() === 'asc' ? (
            <ArrowUp size={12} />
          ) : (
            <ArrowUpDown size={12} />
          )}
        </button>
      ),
      cell: ({ row }) => (
        <span
          className="home-date"
          title={displayDate(row.original.updated_at)}
        >
          {Number.isNaN(Date.parse(row.original.updated_at))
            ? '—'
            : new Date(row.original.updated_at).toLocaleDateString('zh-CN', {
                month: '2-digit',
                day: '2-digit',
                year: 'numeric',
              })}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '操作',
      enableSorting: false,
      cell: ({ row }) => (
        <div className="home-row-actions">
          <Button asChild variant="ghost" size="sm">
            <Link to={`/projects/${row.original.id}/schemes`}>
              管理方案
              <ArrowRight size={13} />
            </Link>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label={`编辑地块${row.original.name}`}
            disabled={USE_MOCK || pending}
            title={
              USE_MOCK ? '离线快照不支持编辑地块，请连接后端。' : '编辑地块条件'
            }
            onClick={() => openEdit(row.original)}
          >
            <Pencil size={14} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="home-delete-button"
            disabled={USE_MOCK || pending}
            aria-label={`删除项目${row.original.name}`}
            title={
              USE_MOCK ? '离线快照不支持删除项目，请连接后端。' : '删除项目'
            }
            onClick={() => {
              deleteProject.reset()
              rememberOpener()
              setDeletingProject(row.original)
            }}
          >
            <Trash2 size={14} />
          </Button>
        </div>
      ),
    },
  ]
  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter: search },
    onSortingChange: setSorting,
    enableSortingRemoval: false,
    globalFilterFn: (row, _columnId, value: string) =>
      `${row.original.name} ${row.original.params.climate_zone ?? ''}`
        .toLocaleLowerCase()
        .includes(value.trim().toLocaleLowerCase()),
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 6 } },
    getRowId: (row) => String(row.id),
  })
  const total = table.getFilteredRowModel().rows.length
  const categoryCounts = {
    all: projectQuery.data?.length ?? 0,
    teaching: projectQuery.data?.filter(isTeachingCase).length ?? 0,
    fictional:
      projectQuery.data?.filter((project) => project.name.includes('虚构'))
        .length ?? 0,
  }
  return (
    <>
      <div className="home-page-heading">
        <div>
          <h1>
            项目总览<span>工作空间</span>
          </h1>
          <p>管理地块与候选方案，让每一次取舍都有依据。</p>
        </div>
        <Button ref={createButton} onClick={openCreate}>
          <Plus size={16} />
          新建项目
        </Button>
      </div>
      {USE_MOCK && (
        <p className="home-preview-note">
          <span />
          当前为离线预览，示例数据仅用于界面与流程体验。
        </p>
      )}
      {notice && (
        <div className="home-notice" role="status">
          <span>{notice}</span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="关闭提示"
            onClick={() => setNotice('')}
          >
            <X size={14} />
          </Button>
        </div>
      )}
      <div className="home-content-grid">
        <section className="home-library" aria-labelledby="projects-title">
          <div className="home-library-heading">
            <div>
              <h2 id="projects-title">我的项目</h2>
              <span>
                {projectQuery.data
                  ? `${projectQuery.data.length} 个项目`
                  : '地块与方案的统一入口'}
              </span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label="刷新项目列表"
              disabled={projectQuery.isFetching}
              onClick={() => void projectQuery.refetch()}
            >
              <RefreshCw
                size={15}
                className={projectQuery.isFetching ? 'home-spin' : undefined}
              />
            </Button>
          </div>
          <div className="home-filters">
            <div
              className="home-filter-tabs"
              role="group"
              aria-label="项目分类"
            >
              {[
                { key: 'all', label: '全部项目' },
                { key: 'teaching', label: '教学案例' },
                { key: 'fictional', label: '虚构示例' },
              ].map((item) => (
                <button
                  key={item.key}
                  aria-pressed={category === item.key}
                  onClick={() => setCategory(item.key)}
                >
                  {item.label}
                  <span>
                    {categoryCounts[item.key as keyof typeof categoryCounts]}
                  </span>
                </button>
              ))}
            </div>
            <div className="home-search">
              <Search size={15} />
              <Input
                aria-label="搜索项目"
                placeholder="搜索项目名称或气候区"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              {search && (
                <button aria-label="清空搜索" onClick={() => setSearch('')}>
                  <X size={13} />
                </button>
              )}
            </div>
          </div>
          {projectQuery.isError ? (
            <div className="home-table-message">
              <HomeErrors error={projectQuery.error} title="项目列表加载失败" />
              <Button
                variant="outline"
                disabled={projectQuery.isFetching}
                onClick={() => void projectQuery.refetch()}
              >
                重新加载
              </Button>
            </div>
          ) : projectQuery.isPending ? (
            <div
              className="home-table-loading"
              role="status"
              aria-label="正在加载项目"
            >
              {[0, 1, 2, 3].map((i) => (
                <div key={i}>
                  <span />
                  <span />
                  <span />
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="home-table-scroll">
                <table className="home-project-table" aria-label="项目列表">
                  <thead>
                    {table.getHeaderGroups().map((group) => (
                      <tr key={group.id}>
                        {group.headers.map((header) => (
                          <th
                            key={header.id}
                            scope="col"
                            aria-sort={
                              header.column.getIsSorted()
                                ? header.column.getIsSorted() === 'desc'
                                  ? 'descending'
                                  : 'ascending'
                                : undefined
                            }
                          >
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext(),
                            )}
                          </th>
                        ))}
                      </tr>
                    ))}
                  </thead>
                  <tbody>
                    {table.getRowModel().rows.map((row) => (
                      <tr
                        key={row.id}
                        data-selected={row.original.id === featured?.id}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id}>
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!total && (
                <div className="home-empty">
                  <FolderOpen size={30} strokeWidth={1.4} />
                  <h3>
                    {projectQuery.data?.length
                      ? '没有找到匹配项目'
                      : '从第一个项目开始'}
                  </h3>
                  <p>
                    {projectQuery.data?.length
                      ? '试试其他名称，或调整案例分类。'
                      : '录入地块条件，再添加几套候选方案。'}
                  </p>
                  <Button
                    variant="outline"
                    onClick={
                      projectQuery.data?.length
                        ? () => {
                            setSearch('')
                            setCategory('all')
                          }
                        : openCreate
                    }
                  >
                    {projectQuery.data?.length ? '清除筛选' : '新建项目'}
                  </Button>
                </div>
              )}
              <div className="home-table-footer">
                <span>
                  {total
                    ? `显示 ${table.getState().pagination.pageIndex * 6 + 1}–${Math.min((table.getState().pagination.pageIndex + 1) * 6, total)} 项，共 ${total} 项`
                    : '0 个匹配项目'}
                </span>
                <div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="上一页"
                    disabled={!table.getCanPreviousPage()}
                    onClick={() => table.previousPage()}
                  >
                    <ChevronLeft size={15} />
                  </Button>
                  <span>
                    {table.getState().pagination.pageIndex + 1} /{' '}
                    {Math.max(1, table.getPageCount())}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="下一页"
                    disabled={!table.getCanNextPage()}
                    onClick={() => table.nextPage()}
                  >
                    <ChevronRight size={15} />
                  </Button>
                </div>
              </div>
            </>
          )}
          <div className="home-library-note">
            <SlidersHorizontal size={15} />
            <span>
              选择项目名称，查看地块与候选方案。
              <span className="home-mobile-table-hint">
                表格可横向滑动，查看面积与操作。
              </span>
            </span>
          </div>
        </section>
        <aside className="home-project-detail" aria-label="当前项目详情">
          <div className="home-detail-heading">
            <span>当前项目</span>
            <span className="home-detail-mark">
              <FolderOpen size={15} />
            </span>
          </div>
          {featured ? (
            <>
              <h2>{featured.name}</h2>
              <span className="home-project-kind">
                {teaching
                  ? '教学推演 · 来源见说明'
                  : fictional
                    ? '虚构示例 · 流程体验'
                    : '项目地块'}
              </span>
              <dl className="home-project-facts">
                <div>
                  <dt>用地面积</dt>
                  <dd>
                    {featured.params.site_area == null ? (
                      '未填写'
                    ) : (
                      <>
                        {featured.params.site_area.toLocaleString('zh-CN')}
                        <small> m²</small>
                      </>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>气候分区</dt>
                  <dd>{featured.params.climate_zone || '未填写'}</dd>
                </div>
                <div>
                  <dt>容积率上限</dt>
                  <dd>{featured.params.far_max ?? '未填写'}</dd>
                </div>
                <div>
                  <dt>建筑限高</dt>
                  <dd>
                    {featured.params.height_max == null ? (
                      '未填写'
                    ) : (
                      <>
                        {featured.params.height_max}
                        <small> m</small>
                      </>
                    )}
                  </dd>
                </div>
              </dl>
              <Button asChild className="home-open-dashboard">
                <Link to={`/projects/${featured.id}/dashboard`}>
                  打开比选看板
                  <ArrowRight size={15} />
                </Link>
              </Button>
              <div className="home-scheme-heading">
                <h3>候选方案</h3>
                <span>
                  {schemeQuery.data ? `${schemeQuery.data.length} 套` : '—'}
                </span>
              </div>
              {schemeQuery.isPending ? (
                <p className="home-small-status" role="status">
                  <LoaderCircle size={14} className="home-spin" />
                  正在读取方案…
                </p>
              ) : schemeQuery.isError ? (
                <div className="home-small-status">
                  <span>方案暂未加载</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void schemeQuery.refetch()}
                  >
                    重试
                  </Button>
                </div>
              ) : schemeQuery.data?.length ? (
                <ul className="home-scheme-list">
                  {schemeQuery.data.slice(0, 4).map((scheme, index) => (
                    <li key={scheme.id}>
                      <span>{String(index + 1).padStart(2, '0')}</span>
                      <div>
                        <strong>{scheme.name}</strong>
                        <small>
                          {scheme.params.structure_type || '结构待填写'}
                          {scheme.params.floors != null
                            ? ` · ${scheme.params.floors} 层`
                            : ''}
                        </small>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="home-small-status">
                  还没有候选方案，可进入方案页添加。
                </p>
              )}
              <Link
                to={`/projects/${featured.id}/schemes`}
                className="home-detail-link"
              >
                管理全部方案
                <ChevronRight size={14} />
              </Link>
              <div className="home-report-links">
                <Link to={`/projects/${featured.id}/chat`}>
                  <MessageSquare size={15} />
                  对话、推演与报告
                  <ArrowRight size={13} />
                </Link>
              </div>
              {(teaching || fictional) && (
                <p className="home-boundary">
                  {teaching
                    ? '候选方案为教学推演，不代表实际建成方案或质量评价。地块背景与假设请核对来源说明。'
                    : '示例参数用于流程体验，专业规则与依据仍需核定。'}
                </p>
              )}
              {projectNotes && (
                <details className="home-source">
                  <summary>来源与适用边界</summary>
                  <p>{projectNotes}</p>
                </details>
              )}
            </>
          ) : (
            <div className="home-detail-empty">
              <Layers3 size={31} strokeWidth={1.4} />
              <p>
                {projectQuery.isPending
                  ? '正在读取项目…'
                  : '建立项目后，在这里查看地块与方案。'}
              </p>
            </div>
          )}
        </aside>
      </div>
      {featured && (
        <details
          className="home-volume"
          key={featured.id}
          open={showVolume}
          onToggle={(event) => setShowVolume(event.currentTarget.open)}
        >
          <summary>
            <Box size={16} />
            <span>参数体量预览</span>
            <small>按已录入方案参数绘制，仅作示意</small>
            <ChevronRight size={15} />
          </summary>
          <div className="home-volume-content">
            {showVolume && (
              <BuildingShowcase
                schemes={schemeQuery.data ?? []}
                pending={schemeQuery.isPending}
                failed={schemeQuery.isError}
                onRetry={() => void schemeQuery.refetch()}
              />
            )}
          </div>
        </details>
      )}
      <div className="home-workspace-note">
        <MapPin size={14} />
        <span>评估范围以项目参数和已录入规则为准，结论可在看板中追溯。</span>
      </div>
      <Dialog
        open={open}
        onOpenChange={(value) => {
          if (!pending) setOpen(value)
        }}
      >
        <DialogContent
          className="home-form-dialog"
          onCloseAutoFocus={restoreFocus}
          showCloseButton={!pending}
          onPointerDownOutside={(event) => event.preventDefault()}
          onEscapeKeyDown={(event) => {
            if (pending) event.preventDefault()
          }}
        >
          <DialogTitle>{editingProject ? '编辑地块' : '新建项目'}</DialogTitle>
          <DialogDescription>
            {editingProject
              ? '更新地块条件后，需要重新评估候选方案。'
              : '记录已知地块条件，创建后即可添加候选方案。'}
          </DialogDescription>
          {open &&
            (schemaQuery.isPending ? (
              <p className="home-small-status" role="status">
                正在加载项目参数…
              </p>
            ) : schemaQuery.data ? (
              <ProjectForm
                key={editingProject?.id ?? 'create'}
                schema={schemaQuery.data.project_params}
                initialValues={editingProject}
                pending={pending}
                error={
                  editingProject ? updateProject.error : createProject.error
                }
                onSubmit={(values) =>
                  editingProject
                    ? updateProject.mutate({ id: editingProject.id, values })
                    : createProject.mutate(values)
                }
                onCancel={() => setOpen(false)}
              />
            ) : (
              <>
                <HomeErrors
                  error={schemaQuery.error}
                  title="项目参数加载失败"
                />
                <Button
                  variant="outline"
                  disabled={schemaQuery.isFetching}
                  onClick={() => void schemaQuery.refetch()}
                >
                  重新加载
                </Button>
              </>
            ))}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!deletingProject}
        onOpenChange={(value) => {
          if (!value && !deleteProject.isPending) setDeletingProject(undefined)
        }}
      >
        <DialogContent
          className="home-delete-dialog"
          onCloseAutoFocus={restoreFocus}
          showCloseButton={!deleteProject.isPending}
          onPointerDownOutside={(event) => event.preventDefault()}
          onEscapeKeyDown={(event) => {
            if (deleteProject.isPending) event.preventDefault()
          }}
        >
          <DialogTitle>删除项目</DialogTitle>
          <DialogDescription>
            确定删除「{deletingProject?.name}」吗？此操作无法撤销。
          </DialogDescription>
          <p className="home-delete-description">
            该项目下的全部方案、评估结果和报告缓存也会一并删除。
          </p>
          <HomeErrors error={deleteProject.error} title="删除未完成" />
          <div className="home-dialog-actions">
            <Button
              variant="outline"
              disabled={deleteProject.isPending}
              onClick={() => setDeletingProject(undefined)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={deleteProject.isPending}
              onClick={() => {
                if (deletingProject && !deleteProject.isPending)
                  deleteProject.mutate(deletingProject)
              }}
            >
              {deleteProject.isPending ? '删除中…' : '确认删除'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
