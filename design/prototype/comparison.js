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
const state = { role: 'government', view: 'matrix', baseline: null, selected: '3', dimension: 2, x: 0, y: 2, includeB: false };
const pointColors = { '1': '#7994b2', '2': '#b78778', '3': '#2676b8', '4': '#3e9e94', '5': '#ad965e' };
const $ = id => document.getElementById(id);
const escapeText = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const evaluation = id => data.evaluation.find(item => item.scheme_id === String(id));
const schemeById = id => schemes.find(item => String(item.id) === String(id));
const score = (id, index) => evaluation(id).dimension_scores[dimensions[index].key];
const current = () => data.roles[state.role];
const ranked = id => current().ranking.find(item => item.scheme_id === String(id));
const excluded = id => current().excluded.some(item => item.scheme_id === String(id));
const one = value => Number(value).toFixed(1);

function heat(value) {
  // One shared linear scale for all dimensions; a color never changes with role.
  const low = [245, 249, 252], high = [43, 105, 155];
  const t = Math.max(0, Math.min(100, value)) / 100;
  return { bg: `rgb(${low.map((v, i) => Math.round(v + (high[i] - v) * t)).join(',')})`, ink: t > .64 ? '#ffffff' : '#2c587b' };
}

function renderMatrix() {
  const first = current().ranking[0].scheme_id;
  const header = schemes.map(s => {
    const id = String(s.id), isExcluded = excluded(id);
    return `<th scope="col" class="${id === first ? 'winner-header' : ''} ${isExcluded ? 'excluded-header' : ''}"><div class="scheme-header"><span class="letter">${s.letter}</span><strong>${escapeText(s.title)}</strong>${isExcluded ? '<span class="scheme-status">硬约束未通过</span>' : `<button class="baseline-button" data-baseline="${id}" aria-pressed="${state.baseline === id}">${state.baseline === id ? '当前基准 ✓' : '设为基准'}</button><span class="scheme-status">${id === first ? '当前第 1 名' : '参与排名'}</span>`}</div></th>`;
  }).join('');
  const rows = dimensions.map((dim, index) => {
    const max = Math.max(...schemes.filter(s => !excluded(s.id)).map(s => score(s.id, index)));
    const cells = schemes.map(s => {
      const id = String(s.id), value = score(id, index), color = heat(value), isExcluded = excluded(id);
      const best = !isExcluded && Math.abs(value - max) < 1e-8;
      const difference = state.baseline ? value - score(state.baseline, index) : null;
      const delta = difference === null ? '' : id === state.baseline ? '比较基准' : `${difference > 0 ? '+' : ''}${one(difference)} 分`;
      return `<td><button class="heat-cell ${isExcluded ? 'excluded-cell' : ''} ${state.selected === id && state.dimension === index ? 'selected' : ''}" style="--cell-bg:${color.bg};--cell-ink:${color.ink}" data-cell="${id}:${index}" aria-label="${escapeText(s.name)}，${dim.name} ${one(value)}分，查看评分依据">${best ? '<span class="best-star" title="合规方案中本维度最高">◆</span>' : ''}<b>${one(value)}</b><span class="cell-note">${best ? '维度领先' : isExcluded ? '仅供参考' : '维度得分'}</span><span class="delta">${delta}</span></button></td>`;
    }).join('');
    return `<tr><th scope="row" class="row-label"><strong>${dim.name}</strong><div class="weight-label">当前权重 <em>${one(current().weights[index] * 100)}%</em></div></th>${cells}</tr>`;
  }).join('');
  const rankings = schemes.map(s => {
    const rank = ranked(s.id);
    return rank ? `<td class="rank-cell ${rank.rank === 1 ? 'winner-rank' : ''}"><div class="rank-line"><b>#${rank.rank}</b><span class="rank-score">${rank.closeness.toFixed(3)}</span></div></td>` : '<td class="rank-cell"><span class="rank-muted">不参与排名</span></td>';
  }).join('');
  $('matrix').innerHTML = `<thead><tr><th class="corner" scope="col"><b>评价维度 ↓</b><small>候选方案 →</small></th>${header}</tr></thead><tbody>${rows}<tr><th class="ranking-label" scope="row">名次 / 贴近度</th>${rankings}</tr></tbody>`;
  $('baseline-note').textContent = state.baseline ? `以 ${schemeById(state.baseline).name} 为基准，格内显示得分差。` : '点击列标题“设为基准”，查看逐项分差。';
  $('clear-baseline').hidden = !state.baseline;
}

function renderDetail() {
  const s = schemeById(state.selected), dim = dimensions[state.dimension], result = evaluation(state.selected);
  const metrics = Object.values(result.metrics).filter(m => m.dimension === dim.key);
  $('cell-detail').innerHTML = `<div class="detail-top"><span>${escapeText(s.name)} / ${dim.name}</span><span class="detail-score">${one(score(s.id, state.dimension))}<small>/ 100</small></span></div><div class="metric-breakdown">${metrics.map(m => `<div class="metric-line"><div><b>${escapeText(m.name.replace('【示例】', ''))} · ${escapeText(m.rule_id)}</b><small>输入值 ${escapeText(m.value)} · 维度内相对权重 ${m.weight_in_dimension}<br>${escapeText(m.formula)}</small></div><span>${m.score === null ? '缺数据' : `${one(m.score)} 分`}</span></div>`).join('')}</div><div class="detail-source">维度分 = 指标分数的加权平均。出处：专业组待确认；当前使用示例评分规则。</div>`;
  const c = score('3', state.dimension), d = score('4', state.dimension), diff = c - d;
  $('reading-insight').innerHTML = `<p class="insight-text"><b>C 的施工友好和绿色低碳得分较高，</b>在当前${roleLabels[state.role]}权重下排第 1。E 的居住品质得分略高于 C，说明四维优势并不都集中在同一套方案。</p><div class="insight-comparison">${dim.name}：C ${one(c)} 分 / D ${one(d)} 分，${Math.abs(diff) < 1e-8 ? '两者相同。' : `C 比 D ${diff > 0 ? '高' : '低'} ${one(Math.abs(diff))} 分。`}</div>`;
}

function makePlot() {
  const W = 740, H = 398, left = 64, top = 40, width = 616, height = 300;
  const x = v => left + width * v / 100, y = v => top + height * (1 - v / 100);
  const active = schemes.filter(s => state.includeB || !excluded(s.id));
  const lines = [0, 25, 50, 75, 100].map(v => `<line x1="${x(v)}" y1="${top}" x2="${x(v)}" y2="${top + height}" stroke="#e2eaf0"/><line x1="${left}" y1="${y(v)}" x2="${left + width}" y2="${y(v)}" stroke="#e2eaf0"/><text x="${x(v)}" y="${top + height + 19}" text-anchor="middle" fill="#8ca1b1" font-size="10">${v}</text><text x="${left - 14}" y="${y(v) + 4}" text-anchor="end" fill="#8ca1b1" font-size="10">${v}</text>`).join('');
  const points = active.map(s => {
    const id = String(s.id), xv = score(id, state.x), yv = score(id, state.y), selected = id === state.selected, color = pointColors[id];
    return `<g class="svg-point" data-point="${id}" role="button" tabindex="0" aria-label="${escapeText(s.name)}，${dimensions[state.x].name} ${one(xv)}分，${dimensions[state.y].name} ${one(yv)}分"><title>${escapeText(s.name)} · ${one(xv)}, ${one(yv)}${excluded(id) ? ' · 未通过硬约束' : ''}</title>${selected ? `<circle cx="${x(xv)}" cy="${y(yv)}" r="18" fill="${color}" fill-opacity=".12"/>` : ''}<circle cx="${x(xv)}" cy="${y(yv)}" r="10" fill="${excluded(id) ? '#fff' : color}" stroke="${color}" stroke-width="2" ${excluded(id) ? 'stroke-dasharray="3 2"' : ''}/><text x="${x(xv)}" y="${y(yv) + 3.5}" text-anchor="middle" fill="${excluded(id) ? color : '#fff'}" font-size="10" font-weight="600" pointer-events="none">${s.letter}</text></g>`;
  }).join('');
  return `<svg id="scatter-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${dimensions[state.x].name}与${dimensions[state.y].name}二维取舍图" style="font-family:Segoe UI,Microsoft YaHei,sans-serif"><rect x="${left}" y="${top}" width="${width}" height="${height}" fill="#f8fbfd" rx="2"/>${lines}<text x="${left}" y="17" fill="#63869f" font-size="11">${dimensions[state.y].name} / 100 分 ↑</text><text x="${left + width}" y="${H - 8}" text-anchor="end" fill="#63869f" font-size="11">${dimensions[state.x].name} / 100 分 →</text>${points}</svg>`;
}

function renderMap() {
  $('plot-wrap').innerHTML = makePlot();
  const active = schemes.filter(s => state.includeB || !excluded(s.id));
  $('map-schemes').innerHTML = active.map(s => `<button class="point-button ${String(s.id) === state.selected ? 'active' : ''}" data-point="${s.id}"><span class="point-dot" style="background:${pointColors[s.id]}"></span>${escapeText(s.name)}<small>${one(score(s.id, state.x))} / ${one(score(s.id, state.y))} 分${excluded(s.id) ? ' · 不参与排名' : ''}</small></button>`).join('') + '<div class="map-selected">位置只反映当前选定的两个维度；完整排名仍由四维权重计算。</div>';
}

function render() {
  $('role-picker').innerHTML = Object.entries(roleLabels).map(([key, label]) => `<button class="role-button ${key === state.role ? 'active' : ''}" data-role="${key}" aria-pressed="${key === state.role}">${label}</button>`).join('');
  $('role-summary').textContent = roleLabels[state.role];
  for (const view of ['matrix', 'map']) {
    $(`view-${view}`).hidden = state.view !== view;
    $(`tab-${view}`).classList.toggle('active', state.view === view);
    $(`tab-${view}`).setAttribute('aria-selected', String(state.view === view));
  }
  $('heat-scale').hidden = state.view !== 'matrix';
  $('view-title').textContent = state.view === 'matrix' ? '5 套方案 × 4 个评价维度' : '在两条轴上，找到方案的位置';
  $('view-description').textContent = state.view === 'matrix' ? '每格是一项维度得分。颜色越深，得分越高；点击格子可看评分依据。' : '每个点代表一套方案。切换横纵轴，观察不同维度之间的取舍；点击点可聚焦方案。';
  renderMatrix(); renderMap(); renderDetail();
}

function matrixSvg() {
  const left = 44, top = 133, labelWidth = 160, cellWidth = 186, rowHeight = 93, headerHeight = 105;
  let content = '';
  const rect = (x,y,w,h,fill) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" stroke="#dfe7ee"/>`;
  const text = (x,y,value,size=14,fill='#486b85',anchor='start',weight=400) => `<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" text-anchor="${anchor}" font-weight="${weight}">${escapeText(value)}</text>`;
  content += rect(left,top,labelWidth,headerHeight,'#f6f9fb') + text(left+18,top+49,'评价维度 ↓',14) + text(left+18,top+71,'候选方案 →',12,'#879ba9');
  schemes.forEach((s,i) => {
    const x = left+labelWidth+cellWidth*i, id=String(s.id);
    content += rect(x,top,cellWidth,headerHeight,excluded(id)?'#faf4f1':ranked(id)?.rank===1?'#e7f1f8':'#f6f9fb');
    content += text(x+cellWidth/2,top+36,s.letter,28,ranked(id)?.rank===1?'#246eaa':'#6f879b','middle',600);
    content += text(x+cellWidth/2,top+59,s.title,13,'#4f6e86','middle');
    content += text(x+cellWidth/2,top+82,excluded(id)?'硬约束未通过':state.baseline===id?'比较基准':`当前第 ${ranked(id).rank} 名`,11,'#8599aa','middle');
  });
  dimensions.forEach((dim,j) => {
    const y=top+headerHeight+j*rowHeight;
    const max=Math.max(...schemes.filter(s=>!excluded(s.id)).map(s=>score(s.id,j)));
    content += rect(left,y,labelWidth,rowHeight,'#f6f9fb') + text(left+18,y+37,dim.name,14) + text(left+18,y+62,`权重 ${one(current().weights[j]*100)}%`,11,'#7e98ab');
    schemes.forEach((s,i) => {
      const id=String(s.id),x=left+labelWidth+cellWidth*i,value=score(id,j),color=heat(value),isExcluded=excluded(id);
      content += rect(x,y,cellWidth,rowHeight,isExcluded?'#f5eeea':color.bg);
      const ink=isExcluded?'#ab8b7c':color.ink;
      content += text(x+cellWidth/2,y+41,one(value),28,ink,'middle',600);
      let note=isExcluded?'仅供参考':value===max?'维度领先':'维度得分';
      if(state.baseline){const delta=value-score(state.baseline,j);note=id===state.baseline?'比较基准':`${delta>0?'+':''}${one(delta)} 分`;}
      content += text(x+cellWidth/2,y+64,note,11,ink,'middle');
    });
  });
  const rankY=top+headerHeight+4*rowHeight;
  content += rect(left,rankY,labelWidth,60,'#f6f9fb')+text(left+18,rankY+34,'名次 / 贴近度',13);
  schemes.forEach((s,i)=>{const rank=ranked(s.id),x=left+labelWidth+cellWidth*i;content+=rect(x,rankY,cellWidth,60,rank?.rank===1?'#e7f1f8':'#f9fbfc')+text(x+cellWidth/2,rankY+35,rank?`#${rank.rank}  /  ${rank.closeness.toFixed(3)}`:'不参与排名',14,rank?'#426e8e':'#ac8776','middle',500);});
  content += text(44,39,'筑衡 · 多方案二维对比',24,'#203e57','start',600)+text(44,68,`当前视角：${roleLabels[state.role]}   |   统一评分刻度 0–100`,13,'#7791a3');
  content += '<defs><linearGradient id="scale"><stop stop-color="#f5f9fc"/><stop offset="1" stop-color="#2b699b"/></linearGradient></defs><rect x="872" y="90" width="140" height="9" fill="url(#scale)"/>' + text(858,99,'0',10,'#8299aa','end') + text(1022,99,'100 分',10,'#8299aa');
  content += text(44,709,'B 方案有硬约束未通过项，维度分数可参考，但默认不参与排名。',12,'#9e8274');
  content += text(44,735,'虚构示例 · 仅供设计讨论，不得用于工程验证或答辩结论。',11,'#97a7b2');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1178" height="762" viewBox="0 0 1178 762" style="font-family:Segoe UI,Microsoft YaHei,sans-serif"><rect width="1178" height="762" fill="#ffffff"/>${content}</svg>`;
}

function exportSvg() {
  let svg=matrixSvg();
  if(state.view==='map'){
    const plot=makePlot().replace(/<svg[^>]*>/,'').replace('</svg>','');
    const legend=schemes.filter(s=>state.includeB||!excluded(s.id)).map((s,i)=>`<text x="${70+i*136}" y="513" fill="${pointColors[s.id]}" font-size="12">${escapeText(s.name)}</text>`).join('');
    svg=`<svg xmlns="http://www.w3.org/2000/svg" width="800" height="570" viewBox="0 0 800 570" style="font-family:Segoe UI,Microsoft YaHei,sans-serif"><rect width="800" height="570" fill="#fff"/><text x="35" y="36" font-size="22" fill="#203e57">筑衡 · 二维取舍图</text><text x="35" y="61" font-size="12" fill="#7993a5">当前视角：${roleLabels[state.role]} · 点的位置只反映两个选定维度</text><g transform="translate(30 90)">${plot}</g>${legend}<text x="35" y="548" font-size="11" fill="#9aaab6">虚构示例 · 仅供设计讨论，不得用于工程验证或答辩结论。</text></svg>`;
  }
  const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download=`筑衡-${state.view==='matrix'?'维度矩阵':'二维取舍图'}-${roleLabels[state.role].replaceAll(' / ','-')}.svg`;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
}

document.addEventListener('click', event => {
  const button=event.target.closest('[data-role],[data-baseline],[data-cell],[data-point]');
  if(!button)return;
  if(button.dataset.role)state.role=button.dataset.role;
  if(button.dataset.baseline)state.baseline=button.dataset.baseline;
  if(button.dataset.cell){const [id,dimension]=button.dataset.cell.split(':');state.selected=id;state.dimension=Number(dimension);}
  if(button.dataset.point){state.selected=button.dataset.point;state.dimension=state.y;}
  render();
});
document.addEventListener('keydown', event => {
  if((event.key==='Enter'||event.key===' ')&&event.target.matches('g[data-point]')){event.preventDefault();state.selected=event.target.dataset.point;state.dimension=state.y;render();}
});
for(const view of ['matrix','map'])$(`tab-${view}`).addEventListener('click',()=>{state.view=view;render();});
$('clear-baseline').addEventListener('click',()=>{state.baseline=null;render();});
for(const axis of ['x','y']){
  $(`axis-${axis}`).innerHTML=dimensions.map((dim,i)=>`<option value="${i}">${dim.name}</option>`).join('');
  $(`axis-${axis}`).value=String(state[axis]);
  $(`axis-${axis}`).addEventListener('change',event=>{
    const other=axis==='x'?'y':'x',previous=state[axis];state[axis]=Number(event.target.value);
    if(state[other]===state[axis]){state[other]=previous;$(`axis-${other}`).value=String(previous);}
    render();
  });
}
$('include-b').addEventListener('change',event=>{state.includeB=event.target.checked;render();});
$('export-button').addEventListener('click',exportSvg);
render();
