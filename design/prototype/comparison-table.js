'use strict';

const tableStatuses = {
  passed: { label: '通过', icon: '✓', style: 'pass' },
  failed: { label: '未通过', icon: '!', style: 'fail' },
  insufficient_data: { label: '数据不足', icon: '—', style: 'missing' },
  not_applicable: { label: '不适用', icon: '·', style: 'neutral' },
};

function tableSchemes() {
  const chosen = schemes.filter(s => state.matrixShown.has(String(s.id)));
  return state.matrixOrder === 'name' ? chosen : chosen.sort((a,b) => (ranked(a.id)?.rank ?? 999) - (ranked(b.id)?.rank ?? 999));
}

function tableRows() {
  const query = state.matrixSearch.trim().toLowerCase();
  const matches = row => !query || `${row.name} ${row.key} ${row.dimension || ''}`.toLowerCase().includes(query);
  if (state.matrixDataset === 'compliance') {
    return data.rules.filter(r => r.type === 'hard').map(r => ({ kind: 'hard', key: r.id, name: r.name.replace('【示例】',''), rule: r })).filter(matches);
  }
  const rows = [];
  dimensions.forEach((dim,index) => {
    if (state.matrixDimension !== 'all' && state.matrixDimension !== dim.key) return;
    const metrics = data.rules.filter(r => r.type === 'metric' && r.dimension === dim.key).map(r => ({ kind: 'metric', key: r.id, name: r.name.replace('【示例】',''), dimension: dim.key, dimensionIndex: index, rule: r }));
    const hits = metrics.filter(matches);
    const dimensionMatch = dim.name.includes(query);
    if (query && !hits.length && !dimensionMatch) return;
    rows.push({ kind: 'dimension', key: `dim-${dim.key}`, name: dim.name, dimension: dim.key, dimensionIndex: index, metricCount: metrics.length });
    if (state.matrixOpen.has(dim.key) || query) rows.push(...(query && !dimensionMatch ? hits : metrics));
  });
  return rows;
}

function tableScore(row, id) {
  return row.kind === 'dimension' ? score(id,row.dimensionIndex) : row.kind === 'metric' ? evaluation(id)?.metrics[row.key]?.score : null;
}

function tableStatus(row,id) {
  const result = evaluation(id)?.compliance.find(rule => rule.rule_id === row.key);
  return tableStatuses[result?.status] || tableStatuses.insufficient_data;
}

function inputValue(metric, id) {
  const value = metric?.value;
  if (!valid(value)) return value == null ? '未提供' : String(value);
  const percentRules = ['Q-01','Q-02','K-01','G-02'];
  if (percentRules.includes(id)) return `${one(value*100)}%`;
  return `${Number.isInteger(value) ? value : one(value)}${({ 'Q-03': ' 户/栋', 'K-02': ' 种', 'S-01': ' 项' })[id] || ''}`;
}

function scoreCell(row,s,shown) {
  const id=String(s.id),selected=state.matrixActive?.scheme===id&&state.matrixActive?.row===row.key;
  let body='',label='';
  if(row.kind==='hard') {
    const status=tableStatus(row,id);
    body=`<span class="rule-state ${status.style}"><i>${status.icon}</i>${status.label}</span>`;
    label=status.label;
  } else {
    const value=tableScore(row,id),baseline=tableScore(row,state.matrixBaseline),difference=valid(value)&&valid(baseline)?value-baseline:null;
    const metric=row.kind==='metric'?evaluation(id)?.metrics[row.key]:null;
    const absent=metric?.status==='not_applicable'?'不适用':'缺数据';
    const relative=state.matrixMode==='difference';
    const best=Math.max(...shown.filter(item=>!excluded(item.id)).map(item=>tableScore(row,item.id)).filter(valid));
    const leading=!excluded(id)&&valid(value)&&Math.abs(value-best)<1e-8;
    const display=relative?difference:value;
    const tone=!valid(display)?'absent':relative?(difference>1e-8?'above':difference< -1e-8?'below':'equal'):'absolute';
    const text=!valid(display)?'—':relative?(state.matrixBaseline===id?'基准':signed(difference)):one(value);
    let note=!valid(value)?absent:relative?`原分 ${one(value)}`:row.kind==='metric'?`输入 ${inputValue(metric,row.key)}`:leading?'已选合规方案中最高':'维度汇总';
    if(relative&&valid(value)&&!valid(baseline))note='基准缺数据';
    const bar=relative?`<div class="cell-tick relative"><i style="--start:${difference<0?50-Math.min(50,Math.abs(difference)/2):50}%;--extent:${valid(difference)?Math.min(50,Math.abs(difference)/2):0}%"></i></div>`:`<div class="cell-tick"><i style="--start:0%;--extent:${valid(value)?Math.max(0,Math.min(100,value)):0}%"></i></div>`;
    body=`<span class="table-cell-value ${tone}">${text}${leading&&!relative?'<small title="已选合规方案中最高">◆</small>':''}</span>${bar}<span class="table-cell-note">${escapeText(note)}</span>`;
    label=relative?`与${schemeById(state.matrixBaseline).letter}比较 ${valid(difference)?`${signed(difference)}分`:'缺数据'}`:valid(value)?`${one(value)}分`:absent;
  }
  return `<td data-column="${id}"><button class="table-score-cell ${selected?'is-selected':''} ${excluded(id)?'reference-cell':''}" data-table-cell="${id}|${row.key}" tabindex="${selected?0:-1}" aria-pressed="${selected}" aria-label="${escapeText(s.name)}，${escapeText(row.name)}，${label}，查看依据">${body}</button></td>`;
}

function renderMatrix() {
  const scroll=document.querySelector('#view-matrix .matrix-scroll'),top=scroll.scrollTop,left=scroll.scrollLeft;
  const shown=tableSchemes(),rows=tableRows();
  const relevant=state.matrixActive&&shown.some(s=>String(s.id)===state.matrixActive.scheme)&&rows.some(row=>row.key===state.matrixActive.row);
  if(!relevant)state.matrixActive=shown.length&&rows.length?{scheme:String(shown.find(s=>String(s.id)===state.selected)?.id||shown[0].id),row:rows[0].key}:null;
  $('matrix-search').value=state.matrixSearch;
  $('clear-search').disabled=!state.matrixSearch;
  $('matrix-order').value=state.matrixOrder;
  $('matrix-baseline').value=state.matrixBaseline;
  $('matrix-baseline').disabled=state.matrixMode!=='difference'||state.matrixDataset==='compliance';
  $('matrix-display').hidden=state.matrixDataset==='compliance';
  $('matrix-baseline-label').hidden=state.matrixDataset==='compliance';
  $('matrix-dimension-filters').hidden=state.matrixDataset==='compliance';
  $('matrix-expansion').hidden=state.matrixDataset==='compliance';
  document.querySelectorAll('[data-dataset]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.dataset===state.matrixDataset)));
  document.querySelectorAll('[data-score-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.scoreMode===state.matrixMode)));
  $('matrix-scheme-filters').innerHTML=schemes.map(s=>`<label class="scheme-filter ${state.matrixShown.has(String(s.id))?'checked':''}"><input type="checkbox" data-table-scheme="${s.id}" ${state.matrixShown.has(String(s.id))?'checked':''}><span>${s.letter}</span>${excluded(s.id)?'<small>参考</small>':''}</label>`).join('');
  $('matrix-dimension-filters').innerHTML=[{key:'all',name:'全部维度'},...dimensions].map(dim=>`<button data-matrix-dimension="${dim.key}" aria-pressed="${state.matrixDimension===dim.key}">${dim.name}</button>`).join('');
  const groups=rows.filter(row=>row.kind==='dimension');
  $('expand-metrics').disabled=!groups.length||groups.every(row=>state.matrixOpen.has(row.dimension))||!!state.matrixSearch.trim();
  $('collapse-metrics').disabled=!groups.some(row=>state.matrixOpen.has(row.dimension))||!!state.matrixSearch.trim();
  $('matrix-result-count').textContent=`${shown.length} 套方案 · ${rows.length} 行结果`;
  $('matrix-empty').hidden=!!(shown.length&&rows.length);
  $('matrix').hidden=!(shown.length&&rows.length);
  if(!shown.length)$('matrix-empty').querySelector('strong').textContent='还没有选择比较方案';
  else $('matrix-empty').querySelector('strong').textContent='没有匹配的指标';
  const header=shown.map(s=>`<th scope="col" data-column="${s.id}" class="${state.matrixActive?.scheme===String(s.id)?'selected-column':''}"><div class="table-scheme-title"><span>${s.letter}</span><strong>${escapeText(s.title)}</strong><small>${ranked(s.id)?`第 ${ranked(s.id).rank} 名 · ${ranked(s.id).closeness.toFixed(3)}`:'硬约束未通过 · 仅参考'}</small></div></th>`).join('');
  const body=rows.map(row=>`<tr class="${row.kind==='dimension'?'dimension-row':'indicator-row'}" data-row="${row.key}"><th scope="row" class="table-row-label">${row.kind==='dimension'?`<button class="dimension-disclosure" data-expand-dimension="${row.dimension}" aria-expanded="${state.matrixOpen.has(row.dimension)||!!state.matrixSearch.trim()}"><span class="disclosure-arrow">${state.matrixOpen.has(row.dimension)||state.matrixSearch.trim()?'⌄':'›'}</span><span><strong>${row.name}</strong><small>${row.metricCount} 项指标 · 权重 ${one(current().weights[row.dimensionIndex]*100)}%</small></span></button>`:`<div class="indicator-label"><strong>${escapeText(row.name.replace(/（.*?）/g,''))}</strong><small>${row.key}${row.kind==='metric'?` · 相对权重 ${row.rule.weight_in_dimension}`:` · ${row.rule.severity==='error'?'错误级':'警告级'}`}</small></div>`}</th>${shown.map(s=>scoreCell(row,s,shown)).join('')}</tr>`).join('');
  $('matrix').innerHTML=`<thead><tr><th class="table-corner" scope="col">${state.matrixDataset==='scores'?'维度 / 评价指标':'硬约束规则'}<small>${state.matrixDataset==='scores'?'汇总行可展开明细':'点状态查看检查依据'}</small></th>${header}</tr></thead><tbody>${body}</tbody>`;
  $('matrix-context').textContent=state.matrixDataset==='compliance'?'不适用表示这条规则无需检查，数据不足表示暂时无法判定。':state.matrixMode==='difference'?`当前差值 = 该方案得分 − ${schemeById(state.matrixBaseline).name}得分。正数为高于基准，负数为低于基准。`:'数字为 0–100 分；小条只辅助读数。违规方案仍可参考得分，但不进入默认排名。';
  scroll.scrollTop=top;scroll.scrollLeft=left;
  renderMatrixInspector();
  if(!exportBusy)$('export-button').disabled=state.view==='matrix'&&(!shown.length||!rows.length);
}

function scoringCurve(row,id) {
  const points=row.rule.scoring?.points,metric=evaluation(id)?.metrics[row.key];
  if(!points?.length)return '';
  const value=metric?.value,lo=Math.min(0,points[0][0],valid(value)?value:Infinity),hi=Math.max(points[points.length-1][0],valid(value)?value:-Infinity);
  const X=v=>38+(v-lo)/(hi-lo||1)*260,Y=v=>140-v*1.02;
  const extended=[[lo,points[0][1]],...points,[hi,points[points.length-1][1]]];
  return `<svg class="scoring-curve" viewBox="0 0 340 174" role="img" aria-label="${escapeText(row.name)}的分段评分曲线"><line x1="38" y1="140" x2="298" y2="140" class="curve-axis"/><line x1="38" y1="38" x2="38" y2="140" class="curve-axis"/><text x="8" y="43">100</text><text x="24" y="144">0</text><polyline points="${extended.map(p=>`${X(p[0])},${Y(p[1])}`).join(' ')}" class="curve-line"/>${points.map(p=>`<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="3" class="curve-control"/>`).join('')}${valid(value)&&valid(metric.score)?`<circle cx="${X(value)}" cy="${Y(metric.score)}" r="6" class="curve-current"/><text x="${Math.min(260,X(value)+8)}" y="${Math.max(20,Y(metric.score)-12)}">当前 ${one(metric.score)} 分</text>`:''}<text x="38" y="160">${lo}</text><text x="298" y="160" text-anchor="end">${hi}</text></svg>`;
}

function matrixInspectorHtml() {
  const active=state.matrixActive,row=tableRows().find(row=>row.key===active?.row);
  if(!row||!active)return '<div class="inspector-empty"><strong>选择一个分数或检查状态</strong><p>这里会显示原始输入、计算方式和依据。</p></div>';
  const s=schemeById(active.scheme),value=tableScore(row,s.id);
  let content='';
  if(row.kind==='dimension') {
    const metrics=Object.values(evaluation(s.id).metrics).filter(m=>m.dimension===row.dimension),total=metrics.filter(m=>valid(m.score)).reduce((sum,m)=>sum+m.weight_in_dimension,0);
    content=`<div class="inspector-number">${one(value)}<small>/ 100 分</small></div><p class="inspector-explanation">维度得分由适用指标按相对权重加权平均。</p><div class="inspector-parts">${metrics.map(m=>`<button data-inspector-metric="${s.id}|${m.rule_id}"><span>${escapeText(m.name.replace('【示例】','').replace(/（.*?）/g,''))}<small>${m.rule_id} · 权重 ${m.weight_in_dimension}${total&&valid(m.score)?`（占 ${one(m.weight_in_dimension/total*100)}%）`:''}</small></span><b>${one(m.score)}</b></button>`).join('')}</div>`;
  } else if(row.kind==='metric') {
    const m=evaluation(s.id).metrics[row.key];
    content=`<div class="inspector-number">${one(m?.score)}<small>/ 100 分</small></div><div class="inspector-fact"><span>方案原始输入</span><b>${escapeText(inputValue(m,row.key))}</b></div><div class="inspector-fact"><span>维度内相对权重</span><b>${row.rule.weight_in_dimension}</b></div>${scoringCurve(row,s.id)}<p class="inspector-explanation">曲线表示输入如何换算成分数，圆点是该方案的位置。</p><details class="inspector-formula"><summary>查看完整公式</summary><p>${escapeText(m?.formula||row.rule.value)}</p></details>`;
  } else {
    const result=evaluation(s.id).compliance.find(rule=>rule.rule_id===row.key),status=tableStatus(row,s.id);
    content=`<span class="inspector-rule-status ${status.style}">${status.icon} ${status.label}</span><p class="inspector-explanation">${escapeText(result?.message||'当前缺少检查结果。')}</p><div class="inspector-fact"><span>实际值</span><b>${valid(result?.value)?result.value:'未单独记录'}</b></div><div class="inspector-fact"><span>判定条件</span><b>${escapeText(result?.limit||row.rule.check)}</b></div><div class="inspector-fact"><span>严重程度</span><b>${row.rule.severity==='error'?'错误级':'警告级'}</b></div><details class="inspector-formula"><summary>查看判定表达式</summary><p>${escapeText(row.rule.check)}${row.rule.when?`<br>适用条件：${escapeText(row.rule.when)}`:''}</p></details>`;
  }
  return `<div class="inspector-heading"><span>${s.letter} 方案 · ${row.kind==='dimension'?'维度汇总':row.key}</span><h3>${escapeText(row.name.replace(/（.*?）/g,''))}</h3></div>${content}<div class="inspector-source"><strong>评分依据</strong><p>当前为示例规则，正式依据待专业组确认。</p>${row.rule?`<details><summary>查看来源记录</summary><p>${escapeText(row.rule.source)}</p></details>`:''}</div>`;
}

function renderMatrixInspector() {
  const scrollTop=$('matrix-detail-dialog').scrollTop;
  const html=matrixInspectorHtml();
  const changed=$('matrix-inspector').innerHTML!==html;
  $('matrix-inspector').innerHTML=html;
  $('matrix-dialog-body').innerHTML=html;
  $('matrix-detail-dialog').scrollTop=scrollTop;
  if(changed&&!window.matchMedia('(prefers-reduced-motion:reduce)').matches)$('matrix-inspector').animate([{opacity:.65},{opacity:1}],{duration:150,easing:'cubic-bezier(0.16,1,0.3,1)'});
}

function selectTableCell(id,key,{sheet=true}={}) {
  state.matrixActive={scheme:String(id),row:key};state.selected=String(id);
  const row=tableRows().find(item=>item.key===key);
  if(row?.dimensionIndex!==undefined)state.dimension=row.dimensionIndex;
  document.querySelectorAll('.table-score-cell').forEach(button=>{
    const selected=button.dataset.tableCell===`${id}|${key}`;
    button.classList.toggle('is-selected',selected);button.tabIndex=selected?0:-1;button.setAttribute('aria-pressed',String(selected));
  });
  document.querySelectorAll('#matrix thead [data-column]').forEach(header=>header.classList.toggle('selected-column',header.dataset.column===String(id)));
  renderMatrixInspector();
  if(sheet&&window.matchMedia('(max-width:1100px)').matches&&!$('matrix-detail-dialog').open)$('matrix-detail-dialog').showModal();
}

function resetMatrix() {
  Object.assign(state,{matrixDataset:'scores',matrixMode:'score',matrixBaseline:current().ranking[0].scheme_id,matrixDimension:'all',matrixSearch:'',matrixOrder:'rank',matrixShown:new Set(schemes.map(s=>String(s.id))),matrixOpen:new Set(['quality']),matrixActive:{scheme:current().ranking[0].scheme_id,row:'dim-quality'}});
  renderMatrix();
}

function initMatrixControls() {
  $('matrix-baseline').innerHTML=schemes.map(s=>`<option value="${s.id}">${escapeText(s.name)}${excluded(s.id)?'（参考）':''}</option>`).join('');
  $('matrix-search').addEventListener('input',event=>{state.matrixSearch=event.target.value;renderMatrix();});
  $('clear-search').addEventListener('click',()=>{state.matrixSearch='';renderMatrix();$('matrix-search').focus();});
  $('matrix-order').addEventListener('change',event=>{state.matrixOrder=event.target.value;renderMatrix();});
  $('matrix-baseline').addEventListener('change',event=>{state.matrixBaseline=event.target.value;renderMatrix();});
  $('matrix-scheme-filters').addEventListener('change',event=>{
    const input=event.target.closest('[data-table-scheme]');if(!input)return;
    const id=input.dataset.tableScheme;input.checked?state.matrixShown.add(id):state.matrixShown.delete(id);renderMatrix();
    document.querySelector(`[data-table-scheme="${id}"]`)?.focus({preventScroll:true});
  });
  $('expand-metrics').addEventListener('click',()=>{dimensions.forEach(dim=>state.matrixOpen.add(dim.key));renderMatrix();});
  $('collapse-metrics').addEventListener('click',()=>{state.matrixOpen.clear();renderMatrix();});
  for(const id of ['reset-matrix','empty-reset'])$(id).addEventListener('click',resetMatrix);
  $('close-matrix-dialog').addEventListener('click',()=>$('matrix-detail-dialog').close());
  document.addEventListener('click',event=>{
    const control=event.target.closest('[data-table-cell],[data-expand-dimension],[data-matrix-dimension],[data-dataset],[data-score-mode],[data-inspector-metric]');if(!control)return;
    if(control.dataset.tableCell){const [id,key]=control.dataset.tableCell.split('|');selectTableCell(id,key);return;}
    if(control.dataset.inspectorMetric){const [id,key]=control.dataset.inspectorMetric.split('|');const row=data.rules.find(r=>r.id===key);if(state.matrixDimension!=='all'&&state.matrixDimension!==row.dimension)state.matrixDimension=row.dimension;state.matrixOpen.add(row.dimension);if(!tableRows().some(item=>item.key===key))state.matrixSearch='';state.matrixActive={scheme:id,row:key};state.selected=id;state.dimension=dimensions.findIndex(dim=>dim.key===row.dimension);renderMatrix();const heading=($('matrix-detail-dialog').open?$('matrix-dialog-body'):$('matrix-inspector')).querySelector('h3');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}return;}
    if(control.dataset.expandDimension){const key=control.dataset.expandDimension;state.matrixOpen.has(key)?state.matrixOpen.delete(key):state.matrixOpen.add(key);renderMatrix();document.querySelector(`[data-expand-dimension="${key}"]`)?.focus({preventScroll:true});return;}
    if(control.dataset.matrixDimension)state.matrixDimension=control.dataset.matrixDimension;
    if(control.dataset.dataset){state.matrixDataset=control.dataset.dataset;state.matrixSearch='';}
    if(control.dataset.scoreMode)state.matrixMode=control.dataset.scoreMode;
    renderMatrix();
  });
  $('matrix').addEventListener('keydown',event=>{
    const cell=event.target.closest('[data-table-cell]');if(!cell)return;
    if(event.key==='Enter'||event.key===' '){event.preventDefault();cell.click();return;}
    if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();const [id,key]=cell.dataset.tableCell.split('|'),columns=tableSchemes(),rows=tableRows();
    let col=columns.findIndex(s=>String(s.id)===id),row=rows.findIndex(r=>r.key===key);
    if(event.key==='ArrowUp')row=Math.max(0,row-1);if(event.key==='ArrowDown')row=Math.min(rows.length-1,row+1);
    if(event.key==='ArrowLeft')col=Math.max(0,col-1);if(event.key==='ArrowRight')col=Math.min(columns.length-1,col+1);
    if(event.key==='Home')col=0;if(event.key==='End')col=columns.length-1;
    const nextId=String(columns[col].id),nextKey=rows[row].key;selectTableCell(nextId,nextKey,{sheet:false});
    const next=document.querySelector(`[data-table-cell="${nextId}|${nextKey}"]`);next?.focus({preventScroll:true});
    if(next){const scroll=document.querySelector('#view-matrix .matrix-scroll'),box=scroll.getBoundingClientRect(),cellBox=next.getBoundingClientRect(),head=$('matrix').querySelector('thead').getBoundingClientRect().height,label=$('matrix').querySelector('.table-corner').getBoundingClientRect().width;if(cellBox.top<box.top+head)scroll.scrollTop+=cellBox.top-box.top-head;if(cellBox.bottom>box.bottom)scroll.scrollTop+=cellBox.bottom-box.bottom;if(cellBox.left<box.left+label)scroll.scrollLeft+=cellBox.left-box.left-label;if(cellBox.right>box.right)scroll.scrollLeft+=cellBox.right-box.right;}
  });
}

function matrixSvg() {
  const shown=tableSchemes(),rows=tableRows(),labelWidth=205,cellWidth=156,left=30,top=124,header=92,rowHeight=65;
  const W=Math.max(730,left*2+labelWidth+shown.length*cellWidth),H=top+header+rows.length*rowHeight+112;
  const text=(x,y,value,size=13,color='#526f82',anchor='start',weight=400)=>`<text x="${x}" y="${y}" font-size="${size}" fill="${color}" text-anchor="${anchor}" font-weight="${weight}">${escapeText(value)}</text>`;
  const rect=(x,y,w,h,fill)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" stroke="#dce5eb"/>`;
  let body=text(30,38,'筑衡 · 指标与依据查询',24,'#203e54','start',600)+text(30,67,`${roleLabels[state.role]}视角 · ${state.matrixDataset==='compliance'?'合规检查':state.matrixMode==='difference'?`得分差 / 以 ${schemeById(state.matrixBaseline).letter} 为基准`:'维度与指标得分'}`,14);
  body+=text(30,95,`${shown.length} 套方案 · ${rows.length} 行结果${state.matrixSearch?` · 搜索：${state.matrixSearch}`:''}`,12,'#7c94a3');
  body+=rect(left,top,labelWidth,header,'#f1f5f7')+text(left+14,top+46,'维度 / 指标',14);
  shown.forEach((s,index)=>{const x=left+labelWidth+index*cellWidth;body+=rect(x,top,cellWidth,header,'#f6f9fa')+text(x+cellWidth/2,top+25,s.letter,23,'#2f6587','middle',600)+text(x+cellWidth/2,top+48,s.title,12,'#617f91','middle')+text(x+cellWidth/2,top+70,ranked(s.id)?`第 ${ranked(s.id).rank} 名`:'未通过硬约束 / 参考',11,'#8c958d','middle');});
  rows.forEach((row,index)=>{const y=top+header+index*rowHeight;body+=rect(left,y,labelWidth,rowHeight,row.kind==='dimension'?'#edf3f7':'#fff')+text(left+13,y+27,row.name.replace(/（.*?）/g,''),13,'#48677e','start',row.kind==='dimension'?600:400)+text(left+13,y+47,row.kind==='dimension'?`权重 ${one(current().weights[row.dimensionIndex]*100)}%`:row.key,11,'#8196a5');shown.forEach((s,col)=>{const x=left+labelWidth+col*cellWidth;let val='',note='',color='#366b8f';if(row.kind==='hard'){const status=tableStatus(row,s.id);val=`${status.icon} ${status.label}`;color=status.style==='fail'?'#a96a56':'#62877b';}else{const value=tableScore(row,s.id),base=tableScore(row,state.matrixBaseline),delta=valid(value)&&valid(base)?value-base:null;val=state.matrixMode==='difference'?(String(s.id)===state.matrixBaseline&&valid(value)?'基准':signed(delta)):one(value);note=!valid(value)?'缺数据':state.matrixMode==='difference'?`原分 ${one(value)}`:row.kind==='metric'?`输入 ${inputValue(evaluation(s.id).metrics[row.key],row.key)}`:'';if(state.matrixMode==='difference'&&valid(delta)&&delta<0)color='#a07c52';}body+=rect(x,y,cellWidth,rowHeight,row.kind==='dimension'?'#f3f7f9':'#fff')+text(x+cellWidth/2,y+30,val,19,color,'middle',600)+text(x+cellWidth/2,y+50,note,10,'#8197a5','middle');});});
  if(!rows.length||!shown.length)body+=text(30,top+header+45,'没有可导出的匹配结果',14);
  body+=text(30,H-54,'缺数据、不适用和未通过硬约束分别呈现；违规方案不参与默认排名。',12,'#8d8075')+text(30,H-26,'虚构示例，仅供设计讨论，不得作为工程验证或答辩结论。',12,'#889da9');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="font-family:Segoe UI,Microsoft YaHei,sans-serif"><rect width="${W}" height="${H}" fill="#fff"/>${body}</svg>`;
}
