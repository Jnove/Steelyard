import { renderToStaticMarkup } from 'react-dom/server'
import { PairPlot, TradeoffPlot } from './ComparisonPlots'
import { finiteScore, rowScore, rowStatus, scoreDifference, scoreText, signedScore, type ComparisonRow, type ComparisonScheme, type ComparisonView, type ScoreMode } from '../../utils/comparison'
import { dimensions, type DimensionKey } from '../../constants/dimensions'

export interface ExportInput {
  view: ComparisonView
  projectName: string
  roleName: string
  criteria?: string[]
  weights?: number[]
  schemes: ComparisonScheme[]
  xAxis: DimensionKey
  yAxis: DimensionKey
  selectedId: string
  first?: ComparisonScheme
  second?: ComparisonScheme
  rows: ComparisonRow[]
  mode: ScoreMode
  baseline?: ComparisonScheme
}

export function comparisonSvg(input: ExportInput): string {
  const matrix = input.view === 'matrix'
  const width = matrix ? Math.max(900, 260 + input.schemes.length * 154) : 1000
  const height = matrix ? 260 + input.rows.length * 66 : 700
  const captions = { map: '二维方案取舍图', pair: '双方案四维差值图', matrix: '指标与合规工作台' }
  const weights = (input.criteria ?? []).map((key, index) => `${dimensions.find(dim => dim.key === key)?.label ?? key} ${finiteScore(input.weights?.[index]) ? (input.weights![index] * 100).toFixed(1) + '%' : '—'}`).join(' · ')
  const svg = <svg xmlns="http://www.w3.org/2000/svg" width={width} height={height} viewBox={`0 0 ${width} ${height}`} fontFamily="Segoe UI, Microsoft YaHei, sans-serif">
    <title>{`${input.projectName} · ${captions[input.view]}`}</title>
    <desc>{`${input.roleName} · ${weights} · ${input.schemes.map(scheme => scheme.name).join('、')}。所有数字取自当前评估与排名结果，未参与排名的方案只作评分参考；规则与专业依据仍需核定。`}</desc>
    <defs><radialGradient id="export-mint" cx="0" cy="0" r="1"><stop stopColor="#ffffff" stopOpacity="0" /><stop offset="1" stopColor="#f8faf9" stopOpacity="0" /></radialGradient><radialGradient id="export-lilac" cx="1" cy="1" r="1"><stop stopColor="#ffffff" stopOpacity="0" /><stop offset="1" stopColor="#f8faf9" stopOpacity="0" /></radialGradient><pattern id="export-reference" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><rect width="3" height="10" fill="#f4dbe1" fillOpacity=".55" /></pattern></defs>
    <rect width={width} height={height} fill="#f8faf9" /><rect width={width} height={height} fill="url(#export-mint)" /><rect width={width} height={height} fill="url(#export-lilac)" />
    <rect x="12" y="12" width={width - 24} height={height - 24} rx="6" fill="#ffffff" stroke="#e4eae8" strokeWidth="1" />
    <text x="30" y="43" fill="#243635" fontSize="21" fontWeight="650">{captions[input.view]}</text>
    <text x="30" y="68" fill="#657572" fontSize="13">{Array.from(input.projectName).slice(0, 70).join('')} · {input.roleName}</text>
    {input.view === 'map' && <svg x="30" y="100" width="940" height="530"><TradeoffPlot schemes={input.schemes} xAxis={input.xAxis} yAxis={input.yAxis} selectedId={input.selectedId} /></svg>}
    {input.view === 'pair' && input.first && input.second && <><text x="30" y="94" fill="#657572" fontSize="13">{input.first.name} − {input.second.name}</text><svg x="30" y="110" width="940" height="514"><PairPlot first={input.first} second={input.second} /></svg></>}
    {matrix && <>
      <text x="30" y="95" fill="#657572" fontSize="13">{input.mode === 'difference' && input.rows[0]?.kind !== 'compliance' ? `分差基准：${input.baseline?.name ?? '无基准数据'}（原分数做差后舍入）` : '点击式工作台的当前筛选范围 · 分数 0–100'}</text>
      {input.schemes.map((scheme, index) => <g key={scheme.id}><rect x={244 + index * 154} y="111" width="145" height="67" rx="4" fill={scheme.color} fillOpacity=".1" stroke="#ffffff" strokeWidth="2" /><text x={255 + index * 154} y="136" fill={scheme.color} fontSize="14" fontWeight="650">{Array.from(scheme.name).slice(0, 13).join('')}</text><text x={255 + index * 154} y="162" fill="#657572" fontSize="11">{scheme.ranked ? `第 ${scheme.ranked.rank} 名 · ${scheme.ranked.closeness.toFixed(3)}` : '未参与排名 · 仅参考'}</text></g>)}
      {input.rows.map((row, index) => <g key={row.key}>
        <rect x="24" y={186 + index * 66} width="212" height="59" rx="4" fill={row.kind === 'dimension' ? '#e4efeb' : '#ffffff'} fillOpacity=".88" stroke="#ffffff" />
        <text x={row.kind === 'metric' ? 42 : 32} y={211 + index * 66} fill="#243635" fontSize="13" fontWeight={row.kind === 'dimension' ? 650 : 400}>{Array.from(row.name).slice(0, 16).join('')}</text>
        <text x="32" y={231 + index * 66} fill="#657572" fontSize="10">{row.kind === 'dimension' ? '维度汇总' : row.key}</text>
        {input.schemes.map((scheme, column) => {
          const score = rowScore(row, scheme), delta = scoreDifference(score, rowScore(row, input.baseline))
          const display = row.kind === 'compliance' ? rowStatus(row, scheme) : input.mode === 'difference'
            ? delta == null ? score == null ? rowStatus(row, scheme) : '基准缺数据' : signedScore(delta)
            : score == null ? rowStatus(row, scheme) : scoreText(score)
          return <g key={scheme.id}><rect x={244 + column * 154} y={186 + index * 66} width="145" height="59" rx="4" fill={scheme.color} fillOpacity=".07" stroke="#ffffff" strokeWidth="2" />
            {scheme.excluded && <rect x={244 + column * 154} y={186 + index * 66} width="145" height="59" rx="4" fill="url(#export-reference)" />}
            <text x={316 + column * 154} y={211 + index * 66} textAnchor="middle" fill={scheme.color} fontSize="17" fontWeight="650">{display}</text>
            <text x={316 + column * 154} y={233 + index * 66} textAnchor="middle" fill="#657572" fontSize="10">{row.kind === 'compliance' ? row.key : `得分 ${scoreText(score)} / 100`}</text>
          </g>
        })}
      </g>)}
    </>}
    {weights && <text x="30" y={height - 58} fill="#657572" fontSize="12">{`当前权重：${weights}`}</text>}
    <text x="30" y={height - 35} fill="#657572" fontSize="12">未参与排名的方案仅作参考；缺值不补零。规则、权重与专业依据仍需核定。</text>
  </svg>
  // React 对项目名、方案名、规则文本进行 XML 转义，导出不包含外部资源或脚本。
  return '<?xml version="1.0" encoding="UTF-8"?>\n' + renderToStaticMarkup(svg)
}
