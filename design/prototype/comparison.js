'use strict';

const data = window.COMPARISON_DATA;
const dimensions = [
  { key: 'quality', name: '居住品质' },
  { key: 'structure', name: '结构安全' },
  { key: 'construction', name: '施工友好' },
  { key: 'green', name: '绿色低碳' },
];
const roleLabels = { government: '政府 / 平台', developer: '开发企业', contractor: '施工总包', resident: '住户' };
const schemes = data.schemes.map(scheme => ({ ...scheme, letter: scheme.name.split(' ')[0], title: scheme.name.substring(scheme.name.indexOf(' ') + 1) }));
const state = { role: 'government', view: 'map', selected: '3', dimension: 2, x: 0, y: 2, includeB: false, pairA: '3', pairB: '4' };
Object.assign(state, {
  matrixDataset: 'scores', matrixMode: 'score', matrixBaseline: '3', matrixDimension: 'all', matrixSearch: '', matrixOrder: 'rank',
  matrixShown: new Set(schemes.map(s => String(s.id))), matrixOpen: new Set(['quality']),
  matrixActive: { scheme: '3', row: 'dim-construction' },
});
const pointColors = { '1': '#7994b2', '2': '#b78778', '3': '#2676b8', '4': '#3e9e94', '5': '#ad965e' };
const $ = id => document.getElementById(id);
const escapeText = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const evaluation = id => data.evaluation.find(item => item.scheme_id === String(id));
const schemeById = id => schemes.find(item => String(item.id) === String(id));
const score = (id, index) => evaluation(id)?.dimension_scores[dimensions[index].key];
const current = () => data.roles[state.role];
const ranked = id => current().ranking.find(item => item.scheme_id === String(id));
const excluded = id => current().excluded.some(item => item.scheme_id === String(id));
const valid = value => typeof value === 'number' && Number.isFinite(value);
const one = value => valid(value) ? value.toFixed(1) : '—';
const isPareto = id => ranked(id)?.is_non_dominated === true;
const pairDifference = index => valid(score(state.pairA, index)) && valid(score(state.pairB, index)) ? score(state.pairA, index) - score(state.pairB, index) : null;
const signed = value => valid(value) ? `${Math.abs(value) < 1e-8 ? '0.0' : `${value > 0 ? '+' : ''}${one(value)}`}` : '—';

function heat(value) {
  if (!valid(value)) return { bg: '#f2f5f7', ink: '#728a9c' };
  // One shared linear scale for all dimensions; a color never changes with role.
  const low = [245, 249, 252], high = [43, 105, 155];
  const t = Math.max(0, Math.min(100, value)) / 100;
  return { bg: `rgb(${low.map((v, i) => Math.round(v + (high[i] - v) * t)).join(',')})`, ink: t > .64 ? '#ffffff' : '#2c587b' };
}

function renderDetail() {
  const s = schemeById(state.selected), dim = dimensions[state.dimension], result = evaluation(state.selected);
  const metrics = Object.values(result.metrics).filter(m => m.dimension === dim.key);
  $('cell-detail').innerHTML = `<div class="detail-top"><span>${escapeText(s.name)} / ${dim.name}</span><span class="detail-score">${one(score(s.id, state.dimension))}<small>/ 100</small></span></div><div class="metric-breakdown">${metrics.map(m => `<div class="metric-line"><div><b>${escapeText(m.name.replace('【示例】', ''))} · ${escapeText(m.rule_id)}</b><small>输入值 ${m.value === null ? '缺数据' : escapeText(m.value)} · 维度内相对权重 ${m.weight_in_dimension}<br>${escapeText(m.formula)}</small></div><span>${!valid(m.score) ? '缺数据' : `${one(m.score)} 分`}</span></div>`).join('')}</div><div class="detail-source">维度分 = 指标分数的加权平均。出处：专业组待确认；当前使用示例评分规则。</div>`;
  const leader = current().ranking[0], leadScheme = schemeById(leader.scheme_id);
  $('reading-insight').innerHTML = `<p class="insight-text"><b>${escapeText(leadScheme.name)}</b>在当前${roleLabels[state.role]}权重下排第 1，贴近度 ${leader.closeness.toFixed(3)}。这是四维得分共同参与排序的结果；单项较高不代表整体第一。</p><div class="insight-comparison">当前选中 ${escapeText(s.name)} 的${dim.name}：${one(score(s.id, state.dimension))} 分。${valid(score(s.id, state.dimension)) ? '展开左侧评分依据，可查看输入值和计算过程。' : '该维度缺少评分数据，不能当作 0 分。'}</div>`;
}

function makePlot() {
  const W = 850, H = 495, left = 60, top = 56, width = 725, height = 362;
  const x = v => left + width * v / 100, y = v => top + height * (1 - v / 100);
  const active = mapSchemes();
  const lines = [0, 25, 50, 75, 100].map(v => `<line x1="${x(v)}" y1="${top}" x2="${x(v)}" y2="${top + height}" stroke="#dce7ee"/><line x1="${left}" y1="${y(v)}" x2="${left + width}" y2="${y(v)}" stroke="#dce7ee"/><text x="${x(v)}" y="${top + height + 25}" text-anchor="middle" fill="#7796aa" font-size="14">${v}</text><text x="${left - 15}" y="${y(v) + 5}" text-anchor="end" fill="#7796aa" font-size="14">${v}</text>`).join('');
  const pointData = active.map(s => ({ s, px: x(score(s.id, state.x)), py: y(score(s.id, state.y)) }));
  const labels = [];
  const collide = (a, b) => a.x < b.x + b.w + 5 && a.x + a.w + 5 > b.x && a.y < b.y + b.h + 5 && a.y + a.h + 5 > b.y;
  const points = pointData.map(({ s, px, py }) => {
    const id = String(s.id), xv = score(id, state.x), yv = score(id, state.y), selected = id === state.selected, color = pointColors[id];
    const label = s.name;
    const w = Array.from(label).reduce((sum, char) => sum + (char.charCodeAt(0) > 255 ? 14 : 8), 12), h = 28;
    const candidates = [[22, -35], [22, 12], [-w - 22, -35], [-w - 22, 12], [22, -67], [-w - 22, 44], [22, 44], [-w - 22, -67]];
    const boxes = candidates.map(([dx, dy]) => ({ x: Math.max(left + 8, Math.min(W - w - 12, px + dx)), y: Math.max(22, Math.min(top + height - h, py + dy)), w, h }));
    const labelBox = boxes.find(box => !labels.some(old => collide(box, old)) && !pointData.some(p => collide(box, { x: p.px - 18, y: p.py - 18, w: 36, h: 36 }))) || boxes[0];
    labels.push(labelBox);
    const lineX = Math.max(labelBox.x, Math.min(labelBox.x + labelBox.w, px));
    const lineY = Math.max(labelBox.y, Math.min(labelBox.y + labelBox.h, py));
    return `<g class="svg-point" data-point="${id}" role="button" tabindex="0" aria-label="${escapeText(s.name)}，${dimensions[state.x].name} ${one(xv)}分，${dimensions[state.y].name} ${one(yv)}分${isPareto(id) ? '，四维非劣' : ''}"><title>${escapeText(s.name)} · ${one(xv)}, ${one(yv)}${excluded(id) ? ' · 硬约束未通过' : isPareto(id) ? ' · 四维非劣' : ''}</title><line x1="${px}" y1="${py}" x2="${lineX}" y2="${lineY}" stroke="${color}" stroke-opacity=".4"/>${selected ? `<circle cx="${px}" cy="${py}" r="25" fill="${color}" fill-opacity=".12"/>` : ''}${isPareto(id) ? `<circle class="pareto-ring" cx="${px}" cy="${py}" r="18" fill="none" stroke="${color}" stroke-width="1.5"/>` : ''}<circle class="point-core" cx="${px}" cy="${py}" r="12" fill="${excluded(id) ? '#fff' : color}" stroke="${color}" stroke-width="2" ${excluded(id) ? 'stroke-dasharray="3 2"' : ''}/><text x="${px}" y="${py + 4}" text-anchor="middle" fill="${excluded(id) ? color : '#fff'}" font-size="12" font-weight="600" pointer-events="none">${s.letter}</text><rect class="point-label-box" x="${labelBox.x}" y="${labelBox.y}" width="${w}" height="${h}" fill="${selected ? '#e6f0f6' : '#fff'}" fill-opacity=".95" rx="3"/><text x="${labelBox.x + 6}" y="${labelBox.y + 19}" fill="${color}" font-size="14" font-weight="${selected ? 600 : 500}" pointer-events="none">${escapeText(label)}</text></g>`;
  }).join('');
  return `<svg id="scatter-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${dimensions[state.x].name}与${dimensions[state.y].name}二维取舍图" style="font-family:Segoe UI,Microsoft YaHei,sans-serif"><rect x="${left}" y="${top}" width="${width}" height="${height}" fill="#f7fafc" rx="2"/>${lines}<text x="${left}" y="22" fill="#4e7895" font-size="15">${dimensions[state.y].name} / 100 分 ↑</text><text x="${left + width}" y="${H - 10}" text-anchor="end" fill="#4e7895" font-size="15">${dimensions[state.x].name} / 100 分 →</text>${points}</svg>`;
}

function mapSchemes() {
  return schemes.filter(s => (state.includeB || !excluded(s.id)) && valid(score(s.id, state.x)) && valid(score(s.id, state.y)));
}

function renderMap() {
  $('plot-wrap').innerHTML = makePlot();
  const active = mapSchemes();
  $('map-schemes').innerHTML = active.map(s => `<button class="point-button ${String(s.id) === state.selected ? 'active' : ''}" data-point="${s.id}" aria-pressed="${String(s.id) === state.selected}"><span class="point-dot" style="background:${pointColors[s.id]}"></span>${escapeText(s.name)}</button>`).join('');
  const missing = schemes.filter(s => (state.includeB || !excluded(s.id)) && (!valid(score(s.id, state.x)) || !valid(score(s.id, state.y))));
  $('map-missing').textContent = missing.length ? `${missing.map(s => s.letter).join('、')} 缺少坐标数据，未绘制` : '';
  const s = schemeById(state.selected), rank = ranked(s.id), target = current().ranking.find(item => item.scheme_id !== state.selected).scheme_id;
  $('map-focus').innerHTML = `<div class="focus-eyebrow">当前选中方案</div><div class="focus-name">${escapeText(s.name)}</div><div class="focus-state"><span>${rank ? `当前第 ${rank.rank} 名` : '不参与排名'}</span>${isPareto(s.id) ? '<span>四维非劣</span>' : ''}</div><div class="focus-scores">${dimensions.map((dim, index) => `<div class="focus-row"><span>${dim.name}</span><b>${one(score(s.id, index))}<small>分</small></b></div>`).join('')}</div><p class="focus-copy">${rank ? `当前${roleLabels[state.role]}视角，贴近度 ${rank.closeness.toFixed(3)}。二维位置展示两项差异，完整排序综合四维权重。` : '硬约束未通过，分数仅供参考；默认不参与排名。'}</p><button class="primary-button" data-compare="${s.id}:${target}">与 ${schemeById(target).letter} 做差值对比</button>`;
}

function makePairPlot() {
  const W = 950, H = 448, left = 152, width = 590, top = 52, rowGap = 88;
  const x = value => left + width * value / 100;
  const a = schemeById(state.pairA), b = schemeById(state.pairB), ca = pointColors[a.id], cb = pointColors[b.id];
  const grid = [0, 25, 50, 75, 100].map(v => `<line x1="${x(v)}" y1="${top}" x2="${x(v)}" y2="${top + rowGap * 4}" stroke="#e0e9ee"/><text x="${x(v)}" y="30" text-anchor="middle" fill="#7692a5" font-size="14">${v}</text>`).join('');
  const rows = dimensions.map((dim, index) => {
    const y = top + 44 + rowGap * index, va = score(a.id, index), vb = score(b.id, index), delta = pairDifference(index);
    const validA = valid(va), validB = valid(vb), same = validA && validB && Math.abs(delta) < 1e-8;
    const points = same ? `<circle cx="${x(va)}" cy="${y}" r="11" fill="${ca}"/><circle cx="${x(vb)}" cy="${y}" r="7" fill="${cb}" stroke="#fff" stroke-width="1.5"/><text x="${x(va)}" y="${y - 22}" text-anchor="middle" fill="#507892" font-size="14">${one(va)} = ${one(vb)}</text>` : `${validA ? `<circle cx="${x(va)}" cy="${y}" r="9" fill="${ca}" stroke="#fff" stroke-width="2"/><text x="${x(va)}" y="${y - 19}" text-anchor="middle" fill="${ca}" font-size="14">${one(va)}</text>` : ''}${validB ? `<circle cx="${x(vb)}" cy="${y}" r="9" fill="${cb}" stroke="#fff" stroke-width="2"/><text x="${x(vb)}" y="${y + 29}" text-anchor="middle" fill="${cb}" font-size="14">${one(vb)}</text>` : ''}`;
    return `<g data-pair-row="${index}" role="button" tabindex="0" class="svg-point" aria-label="${dim.name}，${a.letter} ${one(va)}分，${b.letter} ${one(vb)}分，差值 ${signed(delta)}分，查看评分依据"><title>${dim.name}：${a.letter} ${one(va)} / ${b.letter} ${one(vb)} 分</title><rect x="6" y="${y - 42}" width="930" height="83" fill="${state.dimension === index ? '#edf4f8' : index % 2 === 0 ? '#f7fafb' : '#fff'}" fill-opacity=".7"/><text x="16" y="${y + 5}" fill="#50748b" font-size="16">${dim.name}</text><line x1="${left}" y1="${y}" x2="${left + width}" y2="${y}" stroke="#e0e8ed" stroke-dasharray="3 4"/>${validA && validB ? `<line x1="${x(va)}" y1="${y}" x2="${x(vb)}" y2="${y}" stroke="#87aabd" stroke-width="5" stroke-linecap="round"/>` : ''}${points}<text class="pair-difference" x="873" y="${y + 5}" text-anchor="middle" font-size="20" font-weight="600" fill="${!valid(delta) || same ? '#8196a5' : delta > 0 ? '#326f99' : '#ac7957'}">${signed(delta)}</text></g>`;
  }).join('');
  return `<svg id="pair-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" style="font-family:Segoe UI,Microsoft YaHei,sans-serif" role="img" aria-label="${escapeText(a.name)}与${escapeText(b.name)}四维差值图"><text x="16" y="30" fill="#6b899d" font-size="14">评价维度</text><text x="873" y="30" text-anchor="middle" fill="#6b899d" font-size="14">${a.letter} − ${b.letter} / 分</text>${grid}${rows}<text x="${left + width}" y="${H - 8}" text-anchor="end" fill="#7797aa" font-size="13">统一评分刻度 / 0–100</text></svg>`;
}

function renderPair() {
  $('pair-a').value = state.pairA; $('pair-b').value = state.pairB;
  const a = schemeById(state.pairA), b = schemeById(state.pairB);
  $('pair-key').innerHTML = [a,b].map(s => `<span><i class="point-dot" style="background:${pointColors[s.id]}"></i>${escapeText(s.name)}</span>`).join('');
  const excludedPair = [a,b].filter(s => excluded(s.id));
  $('pair-warning').hidden = !excludedPair.length;
  $('pair-warning').textContent = `${excludedPair.map(s => s.letter).join('、')} 有硬约束未通过项。下面仅对比维度得分，不表示它可进入正式排名。`;
  $('pair-plot').innerHTML = makePairPlot();
  const differences = dimensions.map((dim,i) => ({ name: dim.name, index: i, delta: pairDifference(i) }));
  const wins = differences.filter(d => valid(d.delta) && d.delta > 1e-8), losses = differences.filter(d => valid(d.delta) && d.delta < -1e-8), same = differences.filter(d => valid(d.delta) && Math.abs(d.delta) < 1e-8), missing = differences.filter(d => !valid(d.delta));
  const largest = differences.filter(d => valid(d.delta)).sort((a,b) => Math.abs(b.delta) - Math.abs(a.delta))[0];
  const phrases = [];
  if(wins.length) phrases.push(`${a.letter} 在<strong>${wins.map(d => d.name).join('、')}</strong>得分更高`);
  if(losses.length) phrases.push(`${b.letter} 在<strong>${losses.map(d => d.name).join('、')}</strong>得分更高`);
  if(same.length) phrases.push(`${same.map(d => d.name).join('、')}得分相同`);
  if(missing.length) phrases.push(`${missing.map(d => d.name).join('、')}缺少可比较的分数`);
  $('pair-story').innerHTML = `<h3>${a.letter} 和 ${b.letter}，差在哪里？</h3><p>${phrases.join('；')}。</p><div class="pair-delta-label">${largest ? `最大差距 · ${largest.name}` : '缺少可比较的数据'}</div><span class="pair-largest">${largest ? one(Math.abs(largest.delta)) : '—'} <small>分</small></span><p>${!largest ? '暂无法比较，请补齐评分数据。' : Math.abs(largest.delta) > 1e-8 ? `${largest.delta > 0 ? a.letter : b.letter} 得分更高。` : '两套方案的可比较得分一致。'}<br>点击任一行，可展开当前方案的计算依据。</p>`;
}

let lastRenderedView=null;
let exportBusy=false;
function render() {
  const focus=document.activeElement;
  const restore=focus?.dataset.role?`[data-role="${focus.dataset.role}"]`:focus?.dataset.point?`#scatter-svg [data-point="${focus.dataset.point}"]`:focus?.dataset.pairRow!==undefined?`#pair-svg [data-pair-row="${focus.dataset.pairRow}"]`:null;
  $('role-picker').innerHTML = Object.entries(roleLabels).map(([key, label]) => `<button class="role-button ${key === state.role ? 'active' : ''}" data-role="${key}" aria-pressed="${key === state.role}">${label}</button>`).join('');
  $('role-summary').textContent = roleLabels[state.role];
  for (const view of ['map', 'pair', 'matrix']) {
    $(`view-${view}`).hidden = state.view !== view;
    $(`tab-${view}`).classList.toggle('active', state.view === view);
    $(`tab-${view}`).setAttribute('aria-selected', String(state.view === view));
  }
  $('lower-grid').hidden=state.view==='matrix';
  const copy = {
    map: ['把两项关注点，变成一张取舍地图', '每个点是一套方案。右上方表示两项得分都较高；点击方案，查看它的优势组合。'],
    pair: ['选两套方案，逐项看清差多少', '四个维度各用一条线连接两个分数；右侧差值以“方案一减方案二”计算。'],
    matrix: ['把比较落到每一项指标', '先筛选要比较的方案，再展开维度或搜索指标。点分数，直接查看输入、评分曲线和依据。'],
  };
  $('view-title').textContent = copy[state.view][0];
  $('view-description').textContent = copy[state.view][1];
  renderMatrix(); renderMap(); renderPair(); renderDetail();
  $('export-button').disabled=exportBusy||(state.view==='matrix'&&(!tableSchemes().length||!tableRows().length));
  if(restore)document.querySelector(restore)?.focus({preventScroll:true});
  if(lastRenderedView&&lastRenderedView!==state.view&&!window.matchMedia('(prefers-reduced-motion:reduce)').matches){
    $(`view-${state.view}`).animate([{opacity:.55},{opacity:1}],{duration:250,easing:'cubic-bezier(0.16,1,0.3,1)'});
  }
  lastRenderedView=state.view;
}

async function exportSvg() {
  if(exportBusy)return;
  const button=$('export-button'),status=$('export-status');exportBusy=true;button.disabled=true;button.setAttribute('aria-busy','true');button.dataset.state='loading';status.textContent='';
  await new Promise(resolve=>requestAnimationFrame(resolve));
  try {
  let svg=matrixSvg();
  if(state.view==='map' || state.view==='pair'){
    const isMap=state.view==='map', W=isMap?910:1010, H=isMap?690:710;
    const plot=(isMap?makePlot():makePairPlot()).replace(/<svg[^>]*>/,'').replace('</svg>','');
    const title=isMap?'二维取舍图':`${schemeById(state.pairA).letter} / ${schemeById(state.pairB).letter} 双方案差值图`;
    const legendSchemes=isMap?mapSchemes():[schemeById(state.pairA),schemeById(state.pairB)];
    const legend=legendSchemes.map((s,i)=>`<text x="${35+i*(isMap?160:310)}" y="${isMap?617:566}" fill="${pointColors[s.id]}" font-size="14">${escapeText(s.name)}</text>`).join('');
    const notes=isMap?['双环标记来自四维非劣结果；二维位置仅反映当前选定的两个维度。']:dimensions.map((dim,i)=>`${dim.name}：${schemeById(state.pairA).letter} ${one(score(state.pairA,i))} / ${schemeById(state.pairB).letter} ${one(score(state.pairB,i))} 分，差值 ${signed(pairDifference(i))} 分。`);
    const annotation=notes.map((note,i)=>`<text x="35" y="${(isMap?641:598)+i*19}" font-size="12" fill="#6c8b9f">${escapeText(note)}</text>`).join('');
    svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="font-family:Segoe UI,Microsoft YaHei,sans-serif"><rect width="${W}" height="${H}" fill="#fff"/><text x="35" y="37" font-size="25" fill="#203e57">筑衡 · ${title}</text><text x="35" y="68" font-size="14" fill="#7993a5">当前视角：${roleLabels[state.role]} · 统一评分刻度 0–100</text><g transform="translate(30 103)">${plot}</g>${legend}${annotation}<text x="35" y="${H-18}" font-size="12" fill="#8297a6">虚构示例 · 仅供设计讨论，不得用于工程验证或答辩结论。</text></svg>`;
  }
  const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml;charset=utf-8'}));
  const names={matrix:'指标与依据查询',map:'二维取舍图',pair:'双方案差值图'};
  const a=document.createElement('a');a.href=url;a.download=`筑衡-${names[state.view]}-${roleLabels[state.role].replaceAll(' / ','-')}.svg`;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
  status.setAttribute('role','status');status.dataset.state='success';status.textContent='图已生成，请在浏览器下载记录中查看。';button.dataset.state='success';
  } catch(error) {
    status.setAttribute('role','alert');status.dataset.state='error';status.textContent='没有生成导出文件。请重试，或检查浏览器是否允许下载。';button.dataset.state='error';
  } finally {
    exportBusy=false;button.disabled=state.view==='matrix'&&(!tableRows().length||!tableSchemes().length);button.removeAttribute('aria-busy');
  }
}

document.addEventListener('click', event => {
  const button=event.target.closest('[data-role],[data-point],[data-compare],[data-pair-row]');
  if(!button)return;
  if(button.dataset.role)state.role=button.dataset.role;
  if(button.dataset.point){state.selected=button.dataset.point;state.dimension=state.y;}
  if(button.dataset.compare){[state.pairA,state.pairB]=button.dataset.compare.split(':');state.view='pair';}
  if(button.dataset.pairRow !== undefined){state.selected=state.pairA;state.dimension=Number(button.dataset.pairRow);$('detail-panel').open=true;}
  render();
});
document.addEventListener('keydown', event => {
  if((event.key==='Enter'||event.key===' ')&&event.target.matches('g[data-point],g[data-pair-row]')){event.preventDefault();event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
});
for(const view of ['map','pair','matrix'])$(`tab-${view}`).addEventListener('click',()=>{state.view=view;if(view==='map'&&excluded(state.selected)&&!state.includeB)state.selected=current().ranking[0].scheme_id;render();});
document.querySelector('.view-tabs').addEventListener('keydown',event=>{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();const views=['map','pair','matrix'],index=views.indexOf(state.view);
  const next=event.key==='Home'?0:event.key==='End'?2:(index+(event.key==='ArrowRight'?1:2))%3;
  $(`tab-${views[next]}`).click();$(`tab-${views[next]}`).focus();
});
for(const axis of ['x','y']){
  $(`axis-${axis}`).innerHTML=dimensions.map((dim,i)=>`<option value="${i}">${dim.name}</option>`).join('');
  $(`axis-${axis}`).value=String(state[axis]);
  $(`axis-${axis}`).addEventListener('change',event=>{
    const other=axis==='x'?'y':'x',previous=state[axis];state[axis]=Number(event.target.value);
    if(state[other]===state[axis]){state[other]=previous;$(`axis-${other}`).value=String(previous);}
    render();
  });
}
$('include-b').addEventListener('change',event=>{state.includeB=event.target.checked;if(!state.includeB&&excluded(state.selected))state.selected=current().ranking[0].scheme_id;render();});
for(const side of ['a','b']){
  const key=side==='a'?'pairA':'pairB',other=side==='a'?'pairB':'pairA';
  $(`pair-${side}`).innerHTML=schemes.map(s=>`<option value="${s.id}">${escapeText(s.name)}${excluded(s.id)?'（仅供参考）':''}</option>`).join('');
  $(`pair-${side}`).addEventListener('change',event=>{const previous=state[key];state[key]=event.target.value;if(state[other]===state[key])state[other]=previous;state.selected=state.pairA;render();});
}
$('swap-pair').addEventListener('click',()=>{[state.pairA,state.pairB]=[state.pairB,state.pairA];state.selected=state.pairA;render();});
$('pareto-explanation').addEventListener('click',()=>{const open=$('pareto-help').hidden;$('pareto-help').hidden=!open;$('pareto-explanation').setAttribute('aria-expanded',String(open));});
$('export-button').addEventListener('click',exportSvg);
initMatrixControls();
render();
