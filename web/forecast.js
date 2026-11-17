'use strict';
// The history release and the forecast vintage have separate immutable pointers.
let FORECAST,FORECAST_BASE,HISTORY,forecastScenario='base';
const FC_LABEL={base:'Base · 基准',low:'Low · 较低通胀路径',high:'High · 较高通胀路径'};
Object.assign(LABEL,{model:'模型',asof:'预测基准月',forecast_horizon:'预测步长（月）',
 window_forecast_observations:'窗口含预测同比月数',window_estimated_observations:'窗口含估算同比月数',price_index_lower80:'价格80%下界',price_index_upper80:'价格80%上界',yoy_lower80:'YoY80%下界',yoy_upper80:'YoY80%上界',uncertainty_type:'不确定性口径'});

// Pure display helper: only rendered, visible traces in the selected date range.
function trendAxis(key,series,start,end){
 const floor=key==='t_declines'?6:8,lo=start?String(start).slice(0,7):'',hi=end?String(end).slice(0,7):'9999-12';
 let max=0;for(const trace of series){if(trace.visible===false||trace.visible==='legendonly')continue;
  for(let i=0;i<(trace.y?.length||0);i++){const month=String(trace.x[i]).slice(0,7),v=trace.y[i];if(month>=lo&&month<=hi&&typeof v==='number'&&Number.isFinite(v))max=Math.max(max,v);}}
 const upper=max<=floor?floor:Math.ceil(max*1.12);
 const dtick=upper<=8?1:[2,5,10,20,50,100].find(n=>n>=upper/8)||100;
 return {range:[0,upper],dtick};
}
function syncTrendAxis(key,el){
 const range=el.layout.xaxis.autorange?[]:el.layout.xaxis.range||[];
 const axis=trendAxis(key,el.data,...range);
 if(JSON.stringify(el.layout.yaxis.range)!==JSON.stringify(axis.range)||el.layout.yaxis.dtick!==axis.dtick)
  return Plotly.relayout(el,{'yaxis.range':axis.range,'yaxis.dtick':axis.dtick,'yaxis.autorange':false});
}
// End pure display helper.
function forecastTraces(key,rows,historical,metric,level='both'){
 const first=historical.at(-1),forecastLine=(field,color,width=2)=>({
  x:[first.month,...rows.map(r=>r.month)].map(m=>m+'-01'),y:[first[field],...rows.map(r=>r[field])],
  customdata:['历史边界',...rows.map(r=>`${r.scenario} · Forecast<br>As of ${r.asof} · ${r.model}<br>Model ${FORECAST.meta.model_version} · Generated ${localTime(FORECAST.meta.generated_at)}<br>${stateNote(r)}${r.window_forecast_observations!=null?`<br>60月窗口：预测同比 ${r.window_forecast_observations} 月；估算同比最多 ${r.window_estimated_observations} 月`:''}${r[field+'_lower80']!=null?`<br>80%: ${fmt(r[field+'_lower80'],3)}–${fmt(r[field+'_upper80'],3)}<br>95%: ${fmt(r[field+'_lower95'],3)}–${fmt(r[field+'_upper95'],3)}`:''}`)],
  uid:key+'-forecast-'+field,name:(LABEL[field]||field)+' · Forecast',type:'scatter',mode:'lines',connectgaps:false,
  line:{color,width,dash:'dash'},hovertemplate:`%{x|%Y-%m}<br>${LABEL[field]||field}: %{y:.3f} ${CONFIG[key].unit}<br>%{customdata}<extra></extra>`});
 const result=[];
 if(forecastScenario==='base'&&metric!=='none'){
  for(const [low,high,opacity,name] of [['lower95','upper95',.10,'95% empirical interval'],['lower80','upper80',.20,'80% empirical interval']]){
   if(level!=='both'&&!name.startsWith(level))continue;
   const group=key+'-'+metric+'-'+low;const x=rows.map(r=>r.month+'-01');
   result.push({uid:group+'-lower',legendgroup:group,x,y:rows.map(r=>r[metric+'_'+low]),mode:'lines',line:{width:0},showlegend:false,hoverinfo:'skip',connectgaps:false});
   result.push({uid:group+'-upper',legendgroup:group,x,y:rows.map(r=>r[metric+'_'+high]),mode:'lines',line:{width:0},fill:'tonexty',
    fillcolor:`rgba(112,83,147,${opacity})`,name,hoverinfo:'skip',connectgaps:false});
  }
 }
 if(['measures','acceleration'].includes(key)){
  const colors={p10:'#bacfdb',p25:'#719db9',p75:'#719db9',p90:'#bacfdb',p50:'#173d55',headline:'#b58b40',core:'#9b625b'};
  for(const field of ['p10','p25','p75','p90','p50','headline','core']){
   const trace=forecastLine(field,colors[field],field==='p50'?2.5:2);
   if(['p10','p25','p75','p90'].includes(field))trace.showlegend=false;
   if(['p25','p75','p90'].includes(field)){trace.fill='tonexty';trace.fillcolor=field==='p75'?'rgba(93,147,180,.20)':'rgba(168,201,220,.14)';}
   result.push(trace);
  }
 }else result.push(forecastLine('items_pct','#173d55',2.4),forecastLine('weight_pct','#b58b40',2.4));
 return result;
}

async function renderForecast(){
 const scenario=FORECAST.scenarios[forecastScenario];
 DATA.components=[...HISTORY.components,...scenario.components];
 for(const [key,c] of Object.entries(CONFIG)){
  const rows=scenario.groups[key],hist=HISTORY.groups[key],el=$(`#chart-${key}`),metric=$(`#interval-${key}`).value;
  const isTrend=key.startsWith('t_'),level=$(`#interval-level-${key}`)?.value||'both';
  el._displayRows=[...hist,...rows];
  const previous=new Map(el.data.map(t=>[t.uid,t.visible]));
  let display=[...traces(key,hist).map((t,i)=>({...t,uid:key+'-history-'+i})),...forecastTraces(key,rows,hist,metric,level)];
  const isDistribution=['measures','acceleration'].includes(key);
  if(isDistribution){display=decorateDistribution(key,display);for(const t of display)if(previous.has(t.uid))t.visible=previous.get(t.uid);}
  if(isTrend){for(const t of display){if(t.line?.width>0){const field=t.name.includes('类别')||t.name.includes('items')?'items_pct':'weight_pct';
    t.legendgroup=key+':share:'+field;t.mode='lines+markers';t.marker={size:t.line.dash?4:3,symbol:t.line.dash?'diamond':'circle',color:t.line.color};
    if(t.line.dash)t.showlegend=false;
   }}
   for(const t of display)if(previous.has(t.uid))t.visible=previous.get(t.uid);
   const levelControl=$(`#interval-level-${key}`);levelControl.disabled=metric==='none'||forecastScenario!=='base';
  }
  const layout={...el.layout,width:el.clientWidth,height:el.clientHeight,margin:{l:48,r:16,t:24,b:105},legend:{...el.layout.legend,y:-.24,font:{size:9}},shapes:[...statusShapes(hist),
   {type:'rect',xref:'x',yref:'paper',x0:FORECAST.meta.forecast_start+'-01',x1:FORECAST.meta.forecast_end+'-28',y0:0,y1:1,fillcolor:'rgba(112,83,147,.035)',line:{width:0},layer:'below'},
   {type:'line',xref:'x',yref:'paper',x0:FORECAST.meta.forecast_start+'-01',x1:FORECAST.meta.forecast_start+'-01',y0:0,y1:1,line:{color:'#705393',width:1,dash:'dot'}}],
   annotations:[{xref:'x',yref:'paper',x:FORECAST.meta.forecast_start+'-01',y:1,text:'Forecast →',showarrow:false,xanchor:'left',font:{size:10,color:'#705393'}}]};
  if(key.includes('declines')||key.includes('growth'))layout.yaxis={...layout.yaxis,range:diffusionRange(key,el._displayRows,...(layout.xaxis.autorange?[]:layout.xaxis.range)),autorange:false};
  if(isTrend){layout.margin.b=75;layout.legend={...layout.legend,y:-.18,groupclick:'togglegroup'};layout.yaxis={...layout.yaxis,...trendAxis(key,display,...(layout.xaxis.autorange?[]:layout.xaxis.range)),autorange:false};}
  if(isDistribution)prepareDistribution(key,el,layout);
  await Plotly.react(el,display,layout,{responsive:true,displayModeBar:false});
  if(isDistribution)await attachDistribution(key,el);
  if(isTrend){el._syncTrendAxis=()=>syncTrendAxis(key,el);if(!el._trendEvents){el.on('plotly_restyle',el._syncTrendAxis);el._trendEvents=true;
   el._sizeObserver=new ResizeObserver(()=>{if(el.clientWidth&& (el.layout.width!==el.clientWidth||el.layout.height!==el.clientHeight))Plotly.relayout(el,{width:el.clientWidth,height:el.clientHeight});});el._sizeObserver.observe(el);
  }await el._syncTrendAxis();}
  const intervalCols=metric==='none'?[]:[metric+'_lower80',metric+'_upper80',metric+'_lower95',metric+'_upper95'];
  intervalCols.forEach(k=>LABEL[k]=k.replaceAll('_',' '));
  table($(`#table-${key}`),[...hist,...rows].reverse(),[...c.cols,'data_status','weight_status','uses_estimated_price',...intervalCols,'model','asof']);
  $(`#forecast-card-${key}`).innerHTML=rows.slice(0,2).map(r=>`<span><b>${r.month}</b> ${LABEL[metric==='none'?(key==='measures'||key==='acceleration'?'p50':'weight_pct'):metric]}: <strong>${fmt(r[metric==='none'?(key==='measures'||key==='acceleration'?'p50':'weight_pct'):metric],3)} ${c.unit}</strong></span>`).join('');
 }
 renderComponents();annotateForecastComponents();renderDrivers();
}

function annotateForecastComponents(){if(selectedMonthRows[0]?.data_status==='forecast')$('#component-summary').textContent+=' · Forecast：价格及权重均为预测 · '+FC_LABEL[forecastScenario];}
function renderDrivers(){
 const latest=HISTORY.components.filter(r=>r.month===FORECAST.meta.asof);
 const first=FORECAST.scenarios[forecastScenario].components.filter(r=>r.month===FORECAST.meta.forecast_start);
 const drivers=first.map(r=>({...r,proxy:r.normalized_weight/100*(r.yoy-latest.find(h=>h.code===r.code).yoy)})).sort((a,b)=>Math.abs(b.proxy)-Math.abs(a.proxy)).slice(0,5);
 const near=[...first].sort((a,b)=>Math.abs(Math.abs(a.z_score)-2)-Math.abs(Math.abs(b.z_score)-2)).slice(0,5);
 $('#forecast-drivers').innerHTML=`<div><h4>${FORECAST.meta.forecast_start} · 同比变化驱动</h4><p>加权同比变化代理（pp），用于分项解释，不是分位数的精确贡献。</p>${drivers.map(r=>`<p><b>${esc(r.name)}</b> <span>${fmt(r.proxy,3)} pp · YoY ${fmt(r.yoy,2)}%</span></p>`).join('')}</div><div><h4>t-Diffusion · 临界类别</h4><p>距 |Z| = 2 最近的类别；小幅预测偏差会改变异常归类。</p>${near.map(r=>`<p><b>${esc(r.name)}</b> <span>Z ${fmt(r.z_score,3)} · 权重 ${fmt(r.normalized_weight,2)}%</span></p>`).join('')}</div>`;
}

function researchTables(){
 const f=FORECAST;const route=f.meta.policy;
 const score=f.backtest.filter(r=>r.split==='test');
 const groups=Object.keys(CONFIG).map(g=>{const avg=which=>{const a=score.filter(r=>r.group===g&&r.route===which);return a.reduce((v,r)=>v+r.mae,0)/a.length;};return {group:CONFIG[g].title,bottom_up_mae:avg(route),direct_persistence_mae:avg('direct_flat'),flat_price_mae:avg('flat')};});
 table($('#route-comparison'),groups,['group','bottom_up_mae','direct_persistence_mae','flat_price_mae']);
 const coverage=[1,2,3,6,12,14].map(h=>{const r=f.coverage.filter(r=>r.horizon===h);const n=r.reduce((a,r)=>a+r.n,0);return {horizon:h,evaluated_cells:n,coverage80_pct:100*r.reduce((a,r)=>a+r.n*r.coverage80,0)/n,coverage95_pct:100*r.reduce((a,r)=>a+r.n*r.coverage95,0)/n};});
 table($('#interval-coverage'),coverage,['horizon','evaluated_cells','coverage80_pct','coverage95_pct']);
 table($('#forecast-models'),f.model_selection,['code','selected_model','development_score','development_observations','parameters']);
 $('#backtest-horizon').addEventListener('change',renderBacktest);renderBacktest();
}
function renderBacktest(){const h=Number($('#backtest-horizon').value);const rows=FORECAST.backtest.filter(r=>r.split==='test'&&r.route===FORECAST.meta.policy&&r.horizon===h);table($('#forecast-backtest'),rows,['group','field','horizon','n','mae','rmse','bias','direction_accuracy']);}

async function initForecast(){
 try{
  const response=await fetch('current_forecast.json',{cache:'no-store'});
  if(!response.ok)return;
  const manifest=await response.json();FORECAST_BASE=`forecasts/${manifest.version}/`;
  FORECAST=await fetch(manifest.path).then(r=>{if(!r.ok)throw Error('Forecast vintage not available');return r.json();});
  HISTORY={groups:DATA.groups,components:DATA.components};
  let status;try{status=await fetch('forecast_status.json',{cache:'no-store'}).then(r=>r.json());}catch{}
  const m=FORECAST.meta;
  const panel=document.createElement('section');panel.className='forecast-panel';panel.id='forecast-research';
  panel.innerHTML=`<div class="section-top"><div><span class="eyebrow">FORECAST RESEARCH · V2.0</span><h2>History into the next 14 months</h2><p>历史实线 · 预测虚线 · 竖线区分历史与未来。预测包含已批准的历史估算影响。</p></div><label>Scenario · 情景 <select id="forecast-scenario">${Object.entries(FC_LABEL).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label></div><div class="forecast-meta"><span>基准月 <b>${m.asof}</b></span><span>预测范围 <b>${m.forecast_start}—${m.forecast_end}</b></span><span>模型 <b>${m.model_version} · ${m.policy}</b></span><span>生成 <b>${localTime(m.generated_at)}</b></span><span>更新 <b>${status?.state==='failed'?'失败 · 保留上一版':status?.state==='unchanged'?'输入未变 · 沿用已验证版本':'成功'}</b></span></div><p class="forecast-warning">所有未来价格、权重和指标均为 Forecast。2027年权重采用消费数量不变的价格推算情景，年度BLS新权重尚未公布。80%与95%为联合历史误差路径的经验区间，覆盖率见下方回测；长期及t-Diffusion预测可信度较低。Low/High为完整价格路径情景，不是每个指标的逐点上下界。</p><div class="controls"><a class="button primary" id="forecast-excel" href="${FORECAST_BASE}CPI_Forecast.xlsx" download="CPI_Forecast.xlsx">CPI_Forecast.xlsx ↓</a><a class="button" href="${FORECAST_BASE}Forecast_Indicators.csv" download>Forecast CSV ↓</a><a class="button" href="${FORECAST_BASE}forecast.json" download>JSON ↓</a><a class="button" href="${FORECAST_BASE}Research_Report.md" download>研究报告 ↓</a><a href="forecast_realizations.csv" download>预测实现误差 ↓</a></div><div id="forecast-drivers" class="forecast-drivers"></div><details class="research-detail"><summary>Research & backtest · 模型比较、最终测试及区间覆盖率</summary><p>伪实时扩展窗口回测；已有数据修订，未保存全部官方发布版本。2024年12月前的目标用于选择；2025年1月后的目标用于最终测试。事后插值按依赖月份屏蔽。下表MAE对字段和步长等权平均，单位为%或pp。</p><div class="table-scroll"><table id="route-comparison"></table></div><h4>Held-out empirical interval coverage</h4><p>经验覆盖率按有效指标单元统计；滚动起点相互重叠，单元不是独立样本。${m.calibration_paths}条历史联合误差块重采样成${m.simulated_paths}条路径，模拟条数不等于独立历史样本量。</p><div class="table-scroll"><table id="interval-coverage"></table></div><div class="controls"><label>测试步长 <select id="backtest-horizon">${[1,2,3,6,12,14].map(h=>`<option value="${h}">${h} months</option>`).join('')}</select></label><a href="research/indicator_scores.csv" download>完整指标误差 ↓</a><a href="research/price_scores.csv" download>分项价格及同比误差 ↓</a><a href="research/weighted_scores.csv" download>加权误差 ↓</a><a href="research/diagnostics.csv" download>数据诊断 ↓</a><a href="research/fit_failures.csv" download>拟合回退记录 ↓</a></div><div class="table-scroll"><table id="forecast-backtest"></table></div><h4>Frozen component model selection</h4><div class="table-scroll"><table id="forecast-models"></table></div></details>`;
  $('.status-panel').after(panel);
  for(const [key,c] of Object.entries(CONFIG)){
   const controls=document.createElement('div');controls.className='forecast-chart-tools';
   const fields=key==='measures'||key==='acceleration'?['p50','headline','core','p10','p25','p75','p90']:['weight_pct','items_pct'];
   controls.innerHTML=`<div id="forecast-card-${key}" class="forecast-cards"></div><label>预测经验区间 <select id="interval-${key}">${fields.map(f=>`<option value="${f}">${LABEL[f]}</option>`).join('')}<option value="none">不显示</option></select></label><a href="${FORECAST_BASE+key}_forecast.csv" download>Forecast CSV ↓</a>`;
   $(`#${key} .chart`).before(controls);controls.querySelector('select').addEventListener('change',renderForecast);
   if(['measures','acceleration'].includes(key))controls.querySelector('select').value='none';
   if(key.startsWith('t_')){
    $(`#${key}`).classList.add('trend-chart');const select=controls.querySelector('select');
    select.querySelector('[value="none"]').textContent='趋势研究 · 不显示区间';select.prepend(select.querySelector('[value="none"]'));select.value='none';
    const label=document.createElement('label');label.innerHTML=`区间范围 <select id="interval-level-${key}"><option value="both">80% + 95%</option><option value="80">仅80%</option><option value="95">仅95%</option></select>`;
    controls.append(label);label.querySelector('select').addEventListener('change',renderForecast);
    const note=document.createElement('small');note.textContent='默认趋势模式；经验区间仅适用于Base。点击图例可同时隐藏对应历史及预测线。';controls.append(note);
    const button=document.createElement('button');button.textContent='12M history + Forecast';button.dataset.recentForecast='true';
    $(`#${key} .range-buttons`).prepend(button);button.addEventListener('click',()=>{
     $(`#${key} .range-buttons`).querySelectorAll('button').forEach(b=>b.classList.toggle('active',b===button));
     const start=new Date(FORECAST.meta.asof+'-01T00:00:00Z');start.setUTCMonth(start.getUTCMonth()-11);
     Plotly.relayout(`chart-${key}`,{'xaxis.range':[start.toISOString().slice(0,10),FORECAST.meta.forecast_end+'-28'],'xaxis.autorange':false}).then(()=>$(`#chart-${key}`)._syncTrendAxis());
    });
   }

  }
  const months=[...new Set([...DATA.components.map(r=>r.month),...FORECAST.scenarios.base.components.map(r=>r.month)])].sort().reverse();
  const selected=$('#month-select').value;$('#month-select').innerHTML=months.map(m=>`<option>${m}</option>`).join('');$('#month-select').value=selected;
  $('#forecast-scenario').addEventListener('change',async e=>{forecastScenario=e.target.value;await renderForecast();});
  $('#month-select').addEventListener('change',annotateForecastComponents);researchTables();await renderForecast();
  $('#version').textContent+=` · Forecast ${manifest.version.slice(0,8)} · V2.0`;
 }catch(e){console.error('Forecast loading failed',e);$('#update-message').textContent+=' · 预测读取失败，历史数据仍可用：'+e.message;}
}
window.addEventListener('cpi-history-ready',initForecast,{once:true});
