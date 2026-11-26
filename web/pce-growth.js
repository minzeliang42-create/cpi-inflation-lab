'use strict';
let PCE_GROWTH=null;
function diffusionComparison(cpi,pce){
 const valid=r=>typeof r?.items_pct==='number'&&typeof r?.weight_pct==='number';
 const map=new Map(pce.filter(valid).map(r=>[r.month,r]));const c=[...cpi].reverse().find(r=>valid(r)&&map.has(r.month));
 if(!c)return 'NA：没有两者占比均完整的共同历史月份；保留各自原始历史，不补值。CPI固定68类、单月；PCE为旧金山联储分项、三个月移动平均。';
 const p=map.get(c.month),previous=monthOffset(c.month,-3),a=cpi.find(r=>r.month===previous),b=pce.find(r=>r.month===previous);
 const directions=f=>{if(!valid(a)||!valid(b))return 'NA（历史缺失）';const x=Math.sign(c[f]-a[f]),y=Math.sign(p[f]-b[f]);const word=v=>v>0?'升':v<0?'降':'平';return x===y?'同'+word(x):'分化（CPI'+word(x)+'、PCE'+word(y)+'）';};
 return `${c.month}共同月：CPI/PCE涨价类别${fmt(c.items_pct)}/${fmt(p.items_pct)}%，权重${fmt(c.weight_pct)}/${fmt(p.weight_pct)}%。较${previous}，类别${directions('items_pct')}、权重${directions('weight_pct')}。CPI固定68类、单月；PCE为旧金山联储分项、三个月移动平均。篮子、分类、权重及平滑不同，差异不能全归因基本面；扩散不等于涨幅，亦不证明持续性或因果。`;
}
async function addPceGrowth(){
 const parent=document.getElementById('growth'),box=document.createElement('section');box.id='pce-growth';box.className='pce-growth-addon';box.setAttribute('aria-labelledby','pce-growth-title');
 box.innerHTML='<h4 id="pce-growth-title">PCE Diffusion Growth <span>— San Francisco Fed</span></h4><p class="pce-growth-source">正在读取官方PCE扩散历史…</p><div id="pce-growth-chart" class="chart pce-growth-plot" role="img" aria-label="PCE Diffusion Growth官方历史图"></div><p class="pce-growth-range-note"></p><h4 class="diffusion-comparison-title">CPI vs PCE · Inflation Diffusion Comparison</h4><p id="diffusion-comparison" class="diffusion-comparison"></p><details class="pce-growth-details"><summary>PCE详细数据与来源</summary><div data-pce-growth-detail></div></details>';
 parent.querySelector('.data-panel').before(box);
 try{
 const response=await fetch('pce_growth.json',{cache:'no-store'});if(!response.ok)throw Error('官方历史文件暂不可用');PCE_GROWTH=await response.json();
 const rows=PCE_GROWTH.rows,meta=PCE_GROWTH.meta,cpi=document.getElementById('chart-growth'),pce=document.getElementById('pce-growth-chart');pce._historyRows=rows;
 box.querySelector('.pce-growth-source').textContent=`官方发布口径：三个月移动平均（SF Fed表注） · CPI截至${DATA.groups.growth.at(-1).month}，PCE截至${meta.end} · 单位：%`;
 box.querySelector('[data-pce-growth-detail]').innerHTML=`<p>来源：<a href="${esc(meta.page)}">旧金山联储PCE Inflation Dispersion</a> · <a href="${esc(meta.source)}">官方Excel</a> · <a href="pce_growth.csv" download>PCE Growth历史CSV</a> · <a href="pce_growth.json">字段、来源与缺失记录JSON</a></p><p>${esc(meta.sheet)}：Fraction of items with price increases / Share of expenditures with price increases。原样读取官方发布值，单位已是百分比，不再次平滑。历史${esc(meta.start)}—${esc(meta.end)}；抓取${esc(localTime(meta.fetched_at))}。</p><div class="table-scroll"><table id="pce-growth-table"></table></div>`;
 table(document.getElementById('pce-growth-table'),[...rows].reverse(),['month','items_pct','weight_pct']);
 const x=rows.map(r=>r.month+'-01');const traces=[['items_pct','类别占比','#173d55',2.2],['weight_pct','消费支出权重占比','#b58b40',2.8]].map(([f,name,color,width])=>({x,y:rows.map(r=>r[f]),name,type:'scatter',mode:'lines',connectgaps:false,line:{color,width},hovertemplate:'%{x|%Y-%m}<br>'+name+': %{y:.3f}%<br>SF Fed官方发布值 · 三个月移动平均<extra></extra>'}));
 const latest=historicalWindow(rows)[1];const mirrorRange=(range,end)=>{const start=String(range[0]).slice(0,10),stop=String(range[1]).slice(0,10);return [start,start>end?stop:(stop>end?end:stop)];};
 await Plotly.newPlot(pce,traces,{width:pce.clientWidth,height:pce.clientHeight,paper_bgcolor:'#fff',plot_bgcolor:'#fff',font:{family:'Arial, Microsoft YaHei, sans-serif',size:11,color:'#657681'},margin:{l:48,r:16,t:12,b:75},hovermode:'x unified',xaxis:{type:'date',range:mirrorRange(cpi.layout.xaxis.range,latest),autorange:false,tickformat:'%Y',nticks:8,showgrid:false},yaxis:{range:[0,100],autorange:false,fixedrange:true,ticksuffix:'%',dtick:20,gridcolor:'#e9eef1'},legend:{orientation:'h',x:0,y:-.18,font:{size:11}}},{responsive:true,displayModeBar:false});
 await Plotly.relayout(cpi,{'yaxis.fixedrange':true,'yaxis.range':[0,100]});
 const note=()=>{const lo=String(pce.layout.xaxis.range[0]).slice(0,7),hi=String(pce.layout.xaxis.range[1]).slice(0,7),any=rows.some(r=>r.month>=lo&&r.month<=hi&&(r.items_pct!=null||r.weight_pct!=null));box.querySelector('.pce-growth-range-note').textContent=any?'与上方CPI历史范围联动；各自截止月份保留差异。完整PCE历史可展开或下载。':'NA：当前所选窗口无PCE历史观测，不补值。';};
 let linking=false;for(const [from,to,end] of [[cpi,pce,latest],[pce,cpi,historicalWindow(DATA.groups.growth)[1]]])from.on('plotly_relayout',async event=>{if(linking||!Object.keys(event).some(k=>k.startsWith('xaxis.')))return;linking=true;try{await Plotly.relayout(to,{'xaxis.range':mirrorRange(from.layout.xaxis.range,end),'xaxis.autorange':false});note();}finally{linking=false;}});
 new ResizeObserver(()=>{if(pce.clientWidth&&(Math.abs(pce._fullLayout.width-pce.clientWidth)>1||pce._fullLayout.height!==pce.clientHeight))Plotly.relayout(pce,{width:pce.clientWidth,height:pce.clientHeight});}).observe(pce);
 document.getElementById('diffusion-comparison').textContent=diffusionComparison(DATA.groups.growth,rows);note();
 try{const status=await fetch('pce_growth_status.json',{cache:'no-store'}).then(r=>r.json());if(status.state!=='success')box.querySelector('.pce-growth-source').append(' · 更新失败，保留上次成功数据');}catch{}
 }catch(error){box.querySelector('.pce-growth-source').textContent='PCE：NA · '+error.message+'；原有CPI图与其他研究功能仍可使用。';document.getElementById('diffusion-comparison').textContent='NA：PCE官方历史数据暂不可用，无法进行同月比较。';}
}
if(window.cpiHistoryConfigured)addPceGrowth().catch(console.error);
else window.addEventListener('cpi-history-configured',()=>addPceGrowth().catch(console.error),{once:true});
