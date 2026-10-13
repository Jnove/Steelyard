import { ApiError } from '../api/client'
import type {
  DemoMetadata, EvaluateResponse, ImportResponse, Project, ProjectCreate, RankInput,
  RankResponse, RolesResponse, RulesResponse, SchemaResponse, Scheme, SchemeCreate, WithDemo,
} from '../api/types'
import raw from './fixtures/data.json'
import { topsis } from './topsis'
import { validate, type JsonSchema } from './validation'

interface FixtureBundle {
  fixture_id: string; disclaimer: string; projects: Project[]; schemes: Scheme[]
  evaluation: EvaluateResponse; roles: RolesResponse; ranks: Record<string, RankResponse>
  rules: RulesResponse; schema: SchemaResponse
  defaults: { project: Project['params']; scheme: Scheme['params'] }
  validation: { project: JsonSchema; scheme: JsonSchema }
  imports: { filename: string; sha256: string; schemes: SchemeCreate[];
    project_params: Project['params']; errors: NonNullable<ImportResponse['errors']> }[]
}
const fixture = raw as unknown as FixtureBundle
export const MOCK_STORAGE_KEY = 'zhuheng:t7:mock:v1'
export const mockImportExampleUrl = new URL('./fixtures/demo-import.xlsx', import.meta.url).href
export const mockImportInvalidExampleUrl = new URL('./fixtures/demo-invalid.xlsx', import.meta.url).href
export const mockDisclaimer = fixture.disclaimer
const clone = <T>(value: T): T => structuredClone(value)
const canonical = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`).join(',')}}`
  return JSON.stringify(value) ?? 'undefined'
}
function demo(mode: DemoMetadata['mode'], warnings: string[] = [], unavailable: string[] = []): DemoMetadata {
  return { mode, disclaimer: fixture.disclaimer, fixture_id: fixture.fixture_id, warnings, unavailable }
}
interface State {
  version: 1; fixture_id: string; projects: Project[]; schemes: Scheme[]
  evaluations: Record<string, { fingerprint: string; value: EvaluateResponse }>
  nextProjectId: number; nextSchemeId: number
}
function initial(): State {
  return { version: 1, fixture_id: fixture.fixture_id, projects: clone(fixture.projects), schemes: clone(fixture.schemes),
    evaluations: {}, nextProjectId: 2, nextSchemeId: Math.max(...fixture.schemes.map(s => s.id)) + 1 }
}
function save(state: State): void {
  try { localStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(state)) } catch {
    throw new ApiError(503, { detail: '无法保存演示数据，请允许浏览器本地存储并检查可用空间。', code: 'MOCK_STORAGE_UNAVAILABLE' })
  }
}
function load(): State {
  let serialized: string | null
  try { serialized = localStorage.getItem(MOCK_STORAGE_KEY) } catch {
    throw new ApiError(503, { detail: '浏览器本地存储不可用。', code: 'MOCK_STORAGE_UNAVAILABLE' })
  }
  if (serialized === null) { const state = initial(); save(state); return state }
  let state: State
  try {
    state = JSON.parse(serialized) as State
    if (state.version !== 1 || !Array.isArray(state.projects) || !Array.isArray(state.schemes)
      || !state.evaluations || !Number.isInteger(state.nextProjectId) || !Number.isInteger(state.nextSchemeId)) throw new Error()
  } catch {
    throw new ApiError(409, { detail: '本地演示数据损坏；请备份后重置演示数据。', code: 'MOCK_STORAGE_CORRUPT' })
  }
  // 快照升级时保留用户录入数据，但清除旧计算结果。
  if (state.fixture_id !== fixture.fixture_id) {
    state.fixture_id = fixture.fixture_id; state.evaluations = {}; save(state)
  }
  return state
}
export function resetMockData(): void { save(initial()) }
function projectIn(state: State, id: number): Project {
  const project = state.projects.find(p => p.id === id)
  if (!project) throw new ApiError(404, { detail: `项目 ${id} 不存在` })
  return project
}
function official(state: State, id: number): Scheme[] { return state.schemes.filter(s => s.project_id === id && !s.is_whatif).sort((a, b) => a.id - b.id) }
function fingerprint(state: State, id: number): string {
  return canonical({ params: projectIn(state, id).params, schemes: official(state, id).map(s => ({ id: s.id, name: s.name, params: s.params })) })
}
function invalidate(state: State, id: number): void {
  delete state.evaluations[id]
  projectIn(state, id).updated_at = new Date().toISOString()
}
function nameCheck(name: unknown): asserts name is string {
  validate(name, { type: 'string', minLength: 1, maxLength: 200 }, 'name')
}
function schemeInput(state: State, id: number, input: SchemeCreate, excludeId?: number): void {
  nameCheck(input.name)
  if (state.schemes.some(s => s.project_id === id && s.id !== excludeId && s.name === input.name)) {
    throw new ApiError(409, { detail: `项目内已存在同名方案 ${input.name}` })
  }
  validate(input.params ?? {}, fixture.validation.scheme)
  if (input.is_whatif !== undefined) validate(input.is_whatif, { type: 'boolean' }, 'is_whatif')
  if (input.parent_id != null) validate(input.parent_id, { type: 'integer' }, 'parent_id')
  if (input.parent_id != null && !state.schemes.some(s => s.id === input.parent_id && s.project_id === id)) {
    throw new ApiError(400, { detail: `parent_id ${input.parent_id} 不属于项目 ${id}` })
  }
}
function addScheme(state: State, id: number, input: SchemeCreate): Scheme {
  schemeInput(state, id, input)
  const now = new Date().toISOString()
  const scheme: Scheme = { id: state.nextSchemeId++, project_id: id, name: input.name,
    params: { ...clone(fixture.defaults.scheme), ...input.params }, is_whatif: input.is_whatif ?? false,
    parent_id: input.parent_id ?? null, created_at: now, updated_at: now }
  state.schemes.push(scheme)
  invalidate(state, id)
  return scheme
}

export const projects = {
  async list(): Promise<Project[]> { return clone(load().projects) },
  async get(id: number): Promise<Project> { return clone(projectIn(load(), id)) },
  async create(input: ProjectCreate): Promise<Project> {
    nameCheck(input.name)
    validate(input.params ?? {}, fixture.validation.project)
    const state = load(), now = new Date().toISOString()
    const project: Project = { id: state.nextProjectId++, name: input.name,
      params: { ...clone(fixture.defaults.project), ...input.params }, created_at: now, updated_at: now }
    state.projects.push(project); save(state)
    return clone(project)
  },
}
export const schemes = {
  async list(id: number): Promise<Scheme[]> { const state = load(); projectIn(state, id); return clone(official(state, id)) },
  async create(id: number, input: SchemeCreate): Promise<Scheme> {
    const state = load(); projectIn(state, id)
    const scheme = addScheme(state, id, input); save(state); return clone(scheme)
  },
  async update(id: number, schemeId: number, input: Partial<SchemeCreate>): Promise<Scheme> {
    const state = load(); projectIn(state, id)
    const scheme = state.schemes.find(s => s.project_id === id && s.id === schemeId)
    if (!scheme) throw new ApiError(404, { detail: `方案 ${schemeId} 不属于项目 ${id}` })
    const merged = { ...scheme, ...input }
    schemeInput(state, id, merged, schemeId)
    Object.assign(scheme, { name: merged.name, params: { ...clone(fixture.defaults.scheme), ...merged.params },
      is_whatif: merged.is_whatif, parent_id: merged.parent_id, updated_at: new Date().toISOString() })
    invalidate(state, id); save(state); return clone(scheme)
  },
  async importExcel(id: number, file: File): Promise<WithDemo<ImportResponse>> {
    projectIn(load(), id)
    if (!file.size) throw new ApiError(400, { detail: '上传的文件为空' })
    if (!/\.xlsx$/i.test(file.name)) throw new ApiError(400, { detail: '请上传 .xlsx 工作簿' })
    if (file.size > 10 * 1024 * 1024) throw new ApiError(413, { detail: '离线演示文件上限为 10 MB' })
    if (!globalThis.crypto?.subtle) throw new ApiError(501, { detail: '离线文件识别需要 localhost 或 HTTPS。' })
    const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))].map(b => b.toString(16).padStart(2, '0')).join('')
    const known = fixture.imports.find(item => item.sha256 === hash)
    if (!known) throw new ApiError(422, { detail: '离线模式仅支持原始演示工作簿；任意 Excel 解析请连接后端。',
      code: 'MOCK_IMPORT_UNSUPPORTED', demo: demo('unsupported', ['请选择 demo-import.xlsx；文件修改后需由后端解析。'], ['excel_parsing']) })
    if (known.errors.length) throw new ApiError(422, { detail: { errors: clone(known.errors) } })
    if (!known.schemes.length) throw new ApiError(400, { detail: 'xlsx 里没有任何方案列（方案A-方案F 都为空）' })
    // 哈希计算后重新读取，避免覆盖期间发生的界面写入。
    const state = load(); projectIn(state, id)
    const created = known.schemes.map(input => {
      let name = input.name, n = 2
      while (state.schemes.some(s => s.project_id === id && s.name === name)) name = `${input.name} (${n++})`
      const item = addScheme(state, id, { ...input, name })
      return { id: item.id, name: item.name }
    })
    const project = projectIn(state, id)
    const project_params_updated = Object.values(project.params).every(value => value == null)
    if (project_params_updated) project.params = { ...clone(fixture.defaults.project), ...clone(known.project_params) }
    save(state)
    return { created, errors: [], project_params_updated,
      demo: demo('offline-crud', ['已按演示工作簿的真实解析快照导入；评估已失效。']) }
  },
}

/** 将当前五方案一一映射到快照；项目约束、方案参数和集合必须完全匹配。 */
function matchingInputs(state: State, id: number): Map<string, Scheme> | null {
  if (canonical(projectIn(state, id).params) !== canonical(fixture.projects[0].params)) return null
  const actual = official(state, id), seed = fixture.schemes.filter(s => !s.is_whatif)
  if (actual.length !== seed.length) return null
  const remaining = [...actual], mapping = new Map<string, Scheme>()
  for (const original of seed) {
    const index = remaining.findIndex(s => canonical(s.params) === canonical(original.params))
    if (index < 0) return null
    mapping.set(String(original.id), remaining.splice(index, 1)[0])
  }
  return mapping
}
export const evaluation = {
  async get(id: number): Promise<WithDemo<EvaluateResponse>> {
    const state = load(); projectIn(state, id)
    const cached = state.evaluations[id]
    if (cached && cached.fingerprint === fingerprint(state, id)) return { ...clone(cached.value), demo: demo('engine-fixture') }
    return { project_id: id, rule_count: 0, results: [],
      demo: demo('unsupported', ['尚未评估，或方案修改后评估已失效。'], ['evaluation']) }
  },
  async run(id: number): Promise<WithDemo<EvaluateResponse>> {
    const state = load(); projectIn(state, id)
    if (!official(state, id).length) throw new ApiError(400, { detail: '项目下还没有方案，请先新增或导入方案再评估' })
    const mapping = matchingInputs(state, id)
    if (!mapping) throw new ApiError(409, { detail: '离线模式无法计算新增或修改的参数，请连接真实后端评估；原评估已失效。',
      code: 'MOCK_EVALUATION_UNSUPPORTED', demo: demo('unsupported', ['仅原始五方案与原项目参数的完整集合有真实引擎快照。'], ['evaluation', 'ranking']) })
    const value = clone(fixture.evaluation)
    value.project_id = id
    value.results = value.results.map(result => {
      const scheme = mapping.get(result.scheme_id)!
      return { ...result, scheme_id: String(scheme.id), scheme_name: scheme.name }
    }).sort((a, b) => Number(a.scheme_id) - Number(b.scheme_id))
    state.evaluations[id] = { fingerprint: fingerprint(state, id), value }; save(state)
    return { ...clone(value), demo: demo('engine-fixture') }
  },
}

function normalized(weights: number[]): number[] {
  if (weights.length !== 4 || weights.some(w => !Number.isFinite(w) || w < 0)) throw new ApiError(400, { detail: 'weights 需要四个有限非负数' })
  const sum = weights.reduce((a, b) => a + b, 0)
  if (!Number.isFinite(sum) || sum <= 0) throw new ApiError(400, { detail: '权重总和必须为有限正数' })
  return weights.map(w => w / sum)
}
const sameWeights = (a: number[], b: number[]) => a.length === b.length && a.every((w, i) => Math.abs(w - b[i]) <= 1e-12)
export const ranking = {
  async roles(id: number): Promise<WithDemo<RolesResponse>> { projectIn(load(), id); return { ...clone(fixture.roles), demo: demo('engine-fixture') } },
  async run(id: number, input: RankInput = {}): Promise<RankResponse> {
    if (input.role !== undefined && input.weights !== undefined) throw new ApiError(422, { detail: 'role / weights 二选一' })
    const state = load(); projectIn(state, id)
    const cached = state.evaluations[id], mapping = matchingInputs(state, id)
    if (!cached || cached.fingerprint !== fingerprint(state, id) || !mapping) throw new ApiError(409, {
      detail: '请先评估当前项目；离线排名只支持具有匹配引擎快照的方案集合。', code: 'MOCK_EVALUATION_REQUIRED' })
    let result: RankResponse
    if (input.weights !== undefined) {
      const weights = normalized(input.weights)
      const grids = (await import('./fixtures/grid.json')).default as unknown as RankResponse[]
      const exact = [...Object.values(fixture.ranks), ...grids].find(r => sameWeights(r.weights_used.weights, weights))
      result = clone(exact ?? fixture.ranks.resident)
      result.weights_used = { source: 'weights', criteria: result.criteria, weights, role: null, role_name: null, is_custom: false, note: '', ahp: null, consistency_warning: null }
      if (exact) result.demo = demo('engine-fixture', ['完整分析来自与当前归一化权重精确匹配的引擎快照。'])
      else {
        const start = performance.now()
        const ids = result.scheme_order!
        const rows = ids.map(sid => result.ranking.find(r => r.scheme_id === sid)!)
        result.topsis = topsis(rows.map(r => r.dimension_scores), weights)
        result.ranking = rows.map((row, i) => ({ ...row, closeness: result.topsis.schemes[i].closeness,
          rank: result.topsis.schemes[i].rank, first_place_probability: null }))
        result.sensitivity = null; result.rank_acceptability = null
        result.elapsed_ms = performance.now() - start
        result.demo = demo('custom-topsis', ['浏览器仅用原始引擎维度分重算 TOPSIS；当前权重没有稳健性分析快照。'],
          ['sensitivity', 'flip_points', 'rank_acceptability', 'first_place_probability'])
      }
    } else {
      const role = input.role || 'resident'
      if (!Object.hasOwn(fixture.ranks, role)) throw new ApiError(400, { detail: `没有角色 ${role}` })
      result = clone(fixture.ranks[role]); result.demo = demo('engine-fixture')
    }
    // 动态加载网格期间可能发生编辑，发现变化则拒绝返回过期分析。
    if (fingerprint(load(), id) !== fingerprint(state, id)) throw new ApiError(409, { detail: '方案已变化，请重新评估后排序。' })
    result.project_id = id
    const remap = (sid: string) => String(mapping.get(sid)!.id)
    result.scheme_order = result.scheme_order!.map(remap)
    result.ranking = result.ranking.map(row => ({ ...row, scheme_id: remap(row.scheme_id),
      scheme_name: mapping.get(row.scheme_id)!.name, dominated_by: row.dominated_by.map(remap) }))
    result.excluded = result.excluded.map(row => ({ ...row, scheme_id: remap(row.scheme_id), scheme_name: mapping.get(row.scheme_id)!.name }))
    result.ranking.sort((a, b) => a.rank - b.rank || b.closeness - a.closeness || a.scheme_id.localeCompare(b.scheme_id))
    return result
  },
}
export const rules = { async get(): Promise<WithDemo<RulesResponse>> { return { ...clone(fixture.rules), demo: demo('engine-fixture') } } }
export const schema = { async get(): Promise<SchemaResponse> { return clone(fixture.schema) } }
