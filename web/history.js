'use strict';
let PCE=null;
const HIST_FIELDS=['p10','p25','p75','p90','p50','headline','core'];
function historicalWindow(rows,months=0){const end=rows.at(-1).month+'-01',d=new Date(end+'T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+1);d.setUTCDate(0);const stop=d.toISOString().slice(0,10);const start=new Date(end+'T00:00:00Z');if(months)start.setUTCMonth(start.getUTCMonth()-months+1);return [months?start.toISOString().slice(0,10):rows[0].month+'-01',stop];}
function historyExtent(series,range){const lo=range[0].slice(0,7),hi=range[1].slice(0,7);return series.filter(t=>!t.meta?.shade&&t.visible!==false&&t.visible!=='legendonly').flatMap(t=>t.y.filter((v,i)=>t.x[i].slice(0,7)>=lo&&t.x[i].slice(0,7)<=hi&&typeof v==='number'&&Number.isFinite(v)));}
function historySeries(key,rows){
 const distribution=['measures','acceleration','pce'].includes(key),fields=distribution?HIST_FIELDS:['items_pct','weight_pct'];
 const colors={p10:'#527f9d',p25:'#638aa3',p75:'#638aa3',p90:'#527f9d',p50:'#173d55',headline:'#ac751b',core:'#b44756',items_pct:'#173d55',weight_pct:'#b58b40'};
 const name=f=>({p50:'Median',headline:key==='pce'?'Total PCE':'Headline',core:key==='pce'?'Core PCE':'Core',items_pct:'类别占比',weight_pct:'权重占比'}[f]||f.toUpperCase());
 const x=rows.map(r=>r.month+'-01'),unit=key==='acceleration'?'pp':'%';
 const curves=fields.map(f=>({uid:key+'-'+f,x,y:rows.map(r=>r[f]),meta:{field:f},name:name(f),legendgroup:key+'-'+f,type:'scatter',mode:'lines+markers',connectgaps:false,line:{color:colors[f],width:['p50','headline','core','weight_pct'].includes(f)?2.8:1.4},marker:{size:f==='p50'?4:3,symbol:f==='core'?'diamond':'circle'},customdata:rows.map(r=>key==='pce'?'SF Fed · PCE历史数据':stateNote(r)+(['measures','acceleration'].includes(key)&&(r.headline==null||r.core==null)?'; Headline/Core NA · 官方基期缺失':'')),hovertemplate:'%{x|%Y-%m}<br>'+name(f)+': %{y:.3f} '+unit+'<br>%{customdata}<extra></extra>'}));
 const shades=[];if(distribution)for(const [a,b] of [['p10','p25'],['p25','p75'],['p75','p90']])for(const [f,upper] of [[a,false],[b,true]])shades.push({x,y:rows.map(r=>r[f]),uid:key+'-shade-'+a+'-'+f,meta:{shade:true},legendgroup:key+'-'+b,showlegend:false,hoverinfo:'skip',type:'scatter',mode:'lines',connectgaps:false,line:{width:0},...(upper?{fill:'tonexty',fillcolor:b==='p75'?'rgba(93,147,180,.20)':'rgba(168,201,220,.12)'}:{})});
 return [...shades,...curves];
}
async function syncHistoryAxis(key,el){const box=el._historyBox,manual=el._manualRange;let r;
 const values=historyExtent(el.data,el.layout.xaxis.range);if(manual)r=manual;else if(['growth','declines'].includes(key))r=[0,100];else if(key.startsWith('t_'))r=[0,Math.max(key==='t_growth'?8:6,Math.ceil(Math.max(0,...values)*1.15))];else {let lo=values.length?Math.min(...values):0,hi=values.length?Math.max(...values):1;if(key==='acceleration'){lo=Math.min(0,lo);hi=Math.max(0,hi);}const pad=Math.max(.5,hi-lo)*.1;r=[lo-pad,hi+pad];}
 if(box){box.querySelector('.axis-message').textContent=(manual?'Manual':'Auto · 当前可见历史数据，10%空间')+(values.some(v=>v<r[0]||v>r[1])?'；范围外仍有数据，请Reset或扩大范围。':'');}
 if(JSON.stringify(el.layout.yaxis.range)!==JSON.stringify(r))await Plotly.relayout(el,{'yaxis.range':r,'yaxis.autorange':false});
}
async function configureHistory(key,rows){const el=document.getElementById('chart-'+key);el._historyRows=rows;
 const layout={...el.layout,width:el.clientWidth,height:el.clientHeight,xaxis:{...el.layout.xaxis,range:historicalWindow(rows),autorange:false},yaxis:{...el.layout.yaxis,title:{text:key==='acceleration'?'Percentage points (pp)':key==='pce'||key==='measures'?'YoY (%)':'Share (%)'},zeroline:true,zerolinecolor:'#526b7b',zerolinewidth:1.4},margin:{l:52,r:14,t:16,b:115},legend:{orientation:'h',y:-.23,font:{size:10},groupclick:'togglegroup'}};
 await Plotly.react(el,historySeries(key,rows),layout,{responsive:true,displayModeBar:false});
 if(['measures','acceleration'].includes(key)){const box=document.createElement('div');box.className='axis-settings';box.innerHTML='<button data-auto>Auto Scale</button><label>Y-axis Min <input aria-label="'+key+' Y-axis Min" type="number" step="any" data-min></label><label>Y-axis Max <input aria-label="'+key+' Y-axis Max" type="number" step="any" data-max></label><button data-reset>Reset</button><p class="axis-message" role="status"></p>';el.before(box);el._historyBox=box;
 const reset=()=>{el._manualRange=null;box.querySelectorAll('input').forEach(i=>i.value='');syncHistoryAxis(key,el);};box.querySelector('[data-auto]').onclick=reset;box.querySelector('[data-reset]').onclick=reset;
 box.querySelectorAll('input').forEach(i=>i.oninput=()=>{const a=box.querySelector('[data-min]').value,b=box.querySelector('[data-max]').value;if(a.trim()&&b.trim()&&Number.isFinite(+a)&&Number.isFinite(+b)&&+a<+b){el._manualRange=[+a,+b];syncHistoryAxis(key,el);}else box.querySelector('.axis-message').textContent='请输入有限数值，Min必须小于Max；保留上次有效范围。';});}
 el._distributionRangeChange=async years=>{await Plotly.relayout(el,{'xaxis.range':historicalWindow(rows,years*12),'xaxis.autorange':false});await syncHistoryAxis(key,el);};
 el.on('plotly_restyle',()=>syncHistoryAxis(key,el));el.on('plotly_relayout',e=>{if(Object.keys(e).some(k=>k.startsWith('xaxis.')))syncHistoryAxis(key,el);});await syncHistoryAxis(key,el);
 const observer=new ResizeObserver(()=>{if(el.clientWidth&&Math.abs(el._fullLayout.width-el.clientWidth)>1)Plotly.relayout(el,{width:el.clientWidth,height:el.clientHeight});});observer.observe(el);
}
function monthOffset(month,n){const d=new Date(month+'-01T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+n);return d.toISOString().slice(0,7);}
function historyChange(rows,field,lag){const r=rows.at(-1),p=rows.find(p=>p.month===monthOffset(r.month,-lag));return typeof r[field]==='number'&&typeof p?.[field]==='number'?r[field]-p[field]:null;}
function breadthAnalysis(groups,pce){
 const a=groups.acceleration,g=groups.growth,last=g.at(-1),median=a.at(-1),f=fmt;
 const mean=(offset)=>{const vals=Array.from({length:3},(_,i)=>g.find(r=>r.month===monthOffset(last.month,-offset-i))?.weight_pct);return vals.every(v=>typeof v==='number')?vals.reduce((x,y)=>x+y,0)/3:null;};
 const recent=mean(0),prior=mean(3),delta=recent!=null&&prior!=null?recent-prior:null;
 const previous=g.filter(r=>r.month<last.month&&typeof r.weight_pct==='number'),rank=typeof last.weight_pct==='number'&&previous.length?100*previous.filter(r=>r.weight_pct<=last.weight_pct).length/previous.length:null;
 const state=delta==null||typeof median.p50!=='number'?'NA：比较所需历史不完整':(delta>0?'涨价权重覆盖面扩大':delta<0?'涨价权重覆盖面收缩':'涨价权重覆盖面持平')+'，'+(median.p50>0?'加权中间位置同比较一年前加快':median.p50<0?'加权中间位置同比较一年前放缓':'加权中间位置同比与一年前持平')+'。';
 const p=pce?.at(-1),ptext=p?`可观察事实：PCE截至${p.month}，Total ${f(p.headline)}%、Core ${f(p.core)}%、Median ${f(p.p50)}%；P10/P25/P75/P90为${['p10','p25','p75','p90'].map(k=>f(p[k])).join(' / ')}%。分位数间距反映类别涨幅的分散。${p.p10>0?'解释：最低展示分位数P10仍为正，正涨幅并不限于分布最高端；这不等于每个类别都上涨。':'解释：P10未高于零，分布低端仍存在非正涨幅；不能仅由Total高低判定所有类别的压力。'}`:'PCE：NA，官方文件暂不可用；CPI历史研究继续显示。';
 return `<p>${ptext}</p><p>可观察事实：${median.month} CPI Median Acceleration为<strong>${f(median.p50)} pp</strong>；相较3个月前变化${f(historyChange(a,'p50',3))} pp、12个月前变化${f(historyChange(a,'p50',12))} pp。这是类别加速度的加权中位数，不是两期Median YoY之差，也不表示所有类别同向。</p><p>可观察事实：${last.month}涨价类别占比<strong>${f(last.items_pct)}%</strong>、权重占比<strong>${f(last.weight_pct)}%</strong>。类别占比较3/12个月前变化${f(historyChange(g,'items_pct',3))} / ${f(historyChange(g,'items_pct',12))} pp；权重占比变化${f(historyChange(g,'weight_pct',3))} / ${f(historyChange(g,'weight_pct',12))} pp。</p><p>明确基准：最新3个月权重占比均值${f(recent)}%，前3个月${f(prior)}%，差${f(delta)} pp；“扩大/收缩”按此差的正负判断。当前权重占比在此前历史的经验百分位为${f(rank)}（此前观测≤当期值的占比；≥75为高，≤25为低，其余为中间）。</p><p><strong>定性组合解释：</strong>${state}若覆盖扩大且加速度为正，表示涨价更广且中间位置加快；扩大但为负表示涨价仍扩散但中间位置放缓；收缩但为正表示覆盖收窄同时中间位置加快；收缩且为负表示覆盖收窄且减速。零值单独视为持平，不能强行归入四象限。</p><p>研究推论与限制：类别占比与权重占比背离，可能反映大权重与小权重类别的不同走势，需要分项明细验证。涨价类别多不等于总体通胀高，也不证明持续性。PCE与CPI篮子、支出范围、权重和指数聚合方法不同，且截止月份可不同；本页不加载PCE扩散序列，SF Fed普通PCE Diffusion为3个月移动平均，本站CPI为单月。同期变化不能证明因果，也不是经验证的预测信号。NA表示缺失；CPI已批准估算和暂定权重仍按原口径标记。</p>`;
}
async function startHistory(){
 const grid=document.getElementById('breadth-grid');
 for(const k of ['acceleration','growth']){grid.append(document.getElementById(k));document.querySelector('#'+k+' details').open=false;}
 for(const [key,rows] of Object.entries(DATA.groups))await configureHistory(key,rows);
 try{const r=await fetch('pce.json',{cache:'no-store'});if(!r.ok)throw Error('PCE文件读取失败');PCE=await r.json();
 const p=document.getElementById('pce');p.querySelector('.pce-source').innerHTML=`SF Fed · Level 4 PCE · ${esc(PCE.meta.start)}—${esc(PCE.meta.end)} · 抓取 ${esc(localTime(PCE.meta.fetched_at))}。<a href="${PCE.meta.page}">官方来源</a> · <a href="pce.csv" download>历史CSV</a> · <a href="pce.json">来源/缺失记录JSON</a>`;
 p.querySelector('.pce-latest').textContent=PCE.rows.at(-1).month+' · Total '+fmt(PCE.rows.at(-1).headline)+'% · Core '+fmt(PCE.rows.at(-1).core)+'% · Median '+fmt(PCE.rows.at(-1).p50)+'%';
 await Plotly.newPlot('chart-pce',[],{height:450,paper_bgcolor:'#fff',plot_bgcolor:'#fff',font:{size:10},hovermode:'x unified',xaxis:{type:'date'},yaxis:{ticksuffix:'%'}},{responsive:true,displayModeBar:false});await configureHistory('pce',PCE.rows);table(document.getElementById('table-pce'),[...PCE.rows].reverse(),['month','headline','core','p10','p25','p50','p75','p90']);
 const status=await fetch('pce_status.json',{cache:'no-store'}).then(r=>r.json());if(status.state!=='success')p.querySelector('.pce-source').append(' · 更新失败，保留上次成功数据；检查时间 '+localTime(status.checked_at));
 }catch(e){document.querySelector('.pce-source').textContent='PCE：NA · '+e.message+'；CPI历史图继续可用。';}
 document.getElementById('breadth-analysis').innerHTML=breadthAnalysis(DATA.groups,PCE?.rows);
 const plots=['pce','acceleration','growth'].map(k=>document.getElementById('chart-'+k)).filter(e=>e._historyRows);
 let syncing=false;
 document.querySelectorAll('[data-history-months]').forEach(b=>b.onclick=async()=>{const months=+b.dataset.historyMonths;document.querySelectorAll('[data-history-months]').forEach(x=>x.classList.toggle('active',x===b));const anchor=DATA.groups.growth.at(-1).month,shared=historicalWindow([{month:anchor}],months)[0];syncing=true;try{for(const e of plots){const start=months?shared:e._historyRows[0].month+'-01';await Plotly.relayout(e,{'xaxis.range':[start,historicalWindow(e._historyRows)[1]],'xaxis.autorange':false});await syncHistoryAxis(e.id.replace('chart-',''),e);}}finally{syncing=false;}});
 for(const e of plots){e.on('plotly_relayout',async ev=>{if(syncing||!Object.keys(ev).some(k=>k.startsWith('xaxis.')))return;syncing=true;try{for(const other of plots.filter(p=>p!==e)){const max=historicalWindow(other._historyRows)[1],r=e.layout.xaxis.range;await Plotly.relayout(other,{'xaxis.range':[r[0],String(r[1]).slice(0,10)>max?max:r[1]],'xaxis.autorange':false});}}finally{syncing=false;}});
 e.on('plotly_hover',d=>{if(syncing)return;const x=d.points[0]?.x;if(!x)return;syncing=true;try{for(const other of plots.filter(p=>p!==e)){const points=other.data.flatMap((t,i)=>{const n=t.x.findIndex(m=>m.slice(0,7)===String(x).slice(0,7));return !t.meta?.shade&&n>=0&&t.y[n]!=null?[{curveNumber:i,pointNumber:n}]:[]});if(points.length)Plotly.Fx.hover(other,points);}}finally{syncing=false;}});
 }
 document.querySelector('[data-history-months="36"]').click();
}
window.addEventListener('cpi-history-ready',()=>startHistory().catch(e=>{document.getElementById('breadth-analysis').textContent='分析暂不可用：'+e.message;console.error(e);}));
