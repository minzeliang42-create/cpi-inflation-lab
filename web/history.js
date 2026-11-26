'use strict';
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
async function configureHistory(key,rows){const el=document.getElementById('chart-'+key);el._historyRows=rows;el._historyKey=key;
 const layout={...el.layout,width:el.clientWidth,height:el.clientHeight,xaxis:{...el.layout.xaxis,range:historicalWindow(rows),autorange:false},yaxis:{...el.layout.yaxis,title:{text:key==='acceleration'?'Percentage points (pp)':key==='pce'||key==='measures'?'YoY (%)':'Share (%)'},zeroline:true,zerolinecolor:'#526b7b',zerolinewidth:1.4},margin:{l:52,r:14,t:16,b:115},legend:{orientation:'h',y:-.23,font:{size:10},groupclick:'togglegroup'}};
 await Plotly.react(el,historySeries(key,rows),layout,{responsive:true,displayModeBar:false});
 if(['measures','acceleration'].includes(key)){const box=document.createElement('div');box.className='axis-settings';box.innerHTML='<button data-auto>Auto Scale</button><label>Y-axis Min <input aria-label="'+key+' Y-axis Min" type="number" step="any" data-min></label><label>Y-axis Max <input aria-label="'+key+' Y-axis Max" type="number" step="any" data-max></label><button data-reset>Reset</button><p class="axis-message" role="status"></p>';el.before(box);el._historyBox=box;
 const reset=()=>{el._manualRange=null;box.querySelectorAll('input').forEach(i=>i.value='');syncHistoryAxis(key,el);};box.querySelector('[data-auto]').onclick=reset;box.querySelector('[data-reset]').onclick=reset;
 box.querySelectorAll('input').forEach(i=>i.oninput=()=>{const a=box.querySelector('[data-min]').value,b=box.querySelector('[data-max]').value;if(a.trim()&&b.trim()&&Number.isFinite(+a)&&Number.isFinite(+b)&&+a<+b){el._manualRange=[+a,+b];syncHistoryAxis(key,el);}else box.querySelector('.axis-message').textContent='请输入有限数值，Min必须小于Max；保留上次有效范围。';});}
 el._distributionRangeChange=async years=>{await Plotly.relayout(el,{'xaxis.range':historicalWindow(rows,years*12),'xaxis.autorange':false});await syncHistoryAxis(key,el);};
 el.on('plotly_restyle',()=>syncHistoryAxis(key,el));el.on('plotly_relayout',e=>{if(Object.keys(e).some(k=>k.startsWith('xaxis.')))syncHistoryAxis(key,el);});await syncHistoryAxis(key,el);
 const observer=new ResizeObserver(()=>{if(el.clientWidth&&(Math.abs(el._fullLayout.width-el.clientWidth)>1||Math.abs(el._fullLayout.height-el.clientHeight)>1))Plotly.relayout(el,{width:el.clientWidth,height:el.clientHeight});});observer.observe(el);
}
function monthOffset(month,n){const d=new Date(month+'-01T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+n);return d.toISOString().slice(0,7);}
function historyChange(rows,field,lag){const r=rows.at(-1),p=rows.find(p=>p.month===monthOffset(r.month,-lag));return typeof r[field]==='number'&&typeof p?.[field]==='number'?r[field]-p[field]:null;}
async function startHistory(){
 // Keep all six original CPI sections in 01—06 order. No duplicate topic plots.
 for(const [key,rows] of Object.entries(DATA.groups))await configureHistory(key,rows);
 window.cpiHistoryConfigured=true;window.dispatchEvent(new Event('cpi-history-configured'));
 if(location.hash){const target=document.getElementById(location.hash.slice(1));if(target)target.scrollIntoView({behavior:'instant',block:'start'});}
}
window.addEventListener('cpi-history-ready',()=>startHistory().catch(e=>{document.getElementById('update-message').textContent+=' 历史图初始化失败：'+e.message;console.error(e);}));
