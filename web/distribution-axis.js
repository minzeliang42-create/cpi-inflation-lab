'use strict';
// Presentation only. No transformation of x, y, customdata, or data downloads.
function distributionExtent(series,start,end,includeIntervals=false){
 const lo=start?String(start).slice(0,7):'',hi=end?String(end).slice(0,7):'9999-12';let min=Infinity,max=-Infinity,count=0;
 for(const t of series){if(t.meta?.axisRole==='shade')continue;if(t.visible===false||t.visible==='legendonly'||(!includeIntervals&&t.meta?.axisRole==='interval'))continue;
  for(let i=0;i<(t.y?.length||0);i++){const m=String(t.x[i]).slice(0,7),v=t.y[i];if(m>=lo&&m<=hi&&typeof v==='number'&&Number.isFinite(v)){min=Math.min(min,v);max=Math.max(max,v);count++;}}}
 return count?{min,max,count}:null;
}
function distributionRange(key,series,start,end,includeIntervals=false){
 const extent=distributionExtent(series,start,end,includeIntervals);if(!extent)return key==='acceleration'?[-1,1]:[0,1];
 let {min,max}=extent;if(key==='acceleration'){min=Math.min(0,min);max=Math.max(0,max);}
 const pad=Math.max(max-min,.5)*.1;return [min-pad,max+pad];
}
function validDistributionBounds(min,max){return String(min).trim()!==''&&String(max).trim()!==''&&Number.isFinite(Number(min))&&Number.isFinite(Number(max))&&Number(min)<Number(max);}
function distributionWindow(rows,years){
 const last=new Date(rows.at(-1).month+'-01T00:00:00Z'),first=new Date(rows[0].month+'-01T00:00:00Z');
 const start=new Date(last);start.setUTCMonth(start.getUTCMonth()-(years*12-1));
 const end=new Date(last);end.setUTCMonth(end.getUTCMonth()+1);end.setUTCDate(0);
 return [(years&&start>first?start:first).toISOString().slice(0,10),end.toISOString().slice(0,10)];
}
function decorateDistribution(key,series){
 const fields=['p10','p25','p75','p90','p50','headline','core'];
 const palette={p10:'#527f9d',p25:'#638aa3',p75:'#638aa3',p90:'#527f9d',p50:'#173d55',headline:'#ac751b',core:'#b44756'};
 const shades=[];
 for(const period of ['history','forecast']){
  const curves=series.filter(t=>t.uid.includes('-'+period+'-')&&!t.uid.includes('-lower')&&!t.uid.includes('-upper'));
  const fieldOf=t=>period==='history'?fields[Number(t.uid.split('-').at(-1))]:t.uid.split('-').at(-1);
  const byField=Object.fromEntries(curves.map(t=>[fieldOf(t),t]));
  for(const [low,high] of [['p10','p25'],['p25','p75'],['p75','p90']]){
   if(!byField[low]||!byField[high])continue;
   for(const [field,upper] of [[low,false],[high,true]])shades.push({uid:key+'-'+period+'-shade-'+high+(upper?'-top':'-bottom'),x:byField[field].x,y:byField[field].y,
    type:'scatter',mode:'lines',line:{width:0},showlegend:false,legendgroup:key+'-'+high,hoverinfo:'skip',connectgaps:false,
    meta:{axisRole:'shade'},...(upper?{fill:'tonexty',fillcolor:high==='p75'?'rgba(93,147,180,.16)':'rgba(168,201,220,.10)'}:{})});
  }
 }
 for(const t of series){const interval=t.uid.includes('-lower')||t.uid.includes('-upper');if(interval){t.meta={axisRole:'interval'};continue;}
  const field=t.uid.includes('-history-')?fields[Number(t.uid.split('-').at(-1))]:t.uid.split('-').at(-1);
  const main=['p50','headline','core'].includes(field);t.meta={axisRole:'curve',field,main};t.legendgroup=key+'-'+field;
  t.line={...t.line,color:palette[field],width:main?(field==='p50'?3.4:3):1.5};
  t.name=({p50:'Median',headline:'Headline',core:'Core'}[field]||field.toUpperCase())+(t.uid.includes('-forecast-')?' · Forecast':'');
  t.showlegend=!t.uid.includes('-forecast-');t.mode='lines+markers';t.cliponaxis=false;
  if(typeof HISTORY!=='undefined'&&HISTORY){t.customdata=t.customdata?.map((text,i)=>{const month=String(t.x[i]).slice(0,7);const row=HISTORY.groups[key].find(r=>r.month===month)||FORECAST.scenarios.base.groups[key].find(r=>r.month===month);const gaps=row?['headline','core'].filter(f=>row[f]==null):[];return text+(gaps.length?'<br>'+gaps.map(f=>f==='core'?'Core: NA':'Headline: NA').join('；')+'（所需官方指数/基期缺失，未补值）':'');});}
  t.marker={size:main?4.5:3.6,symbol:({p10:'triangle-down',p25:'circle-open',p75:'square-open',p90:'triangle-up',core:'diamond',headline:'square',p50:'circle'})[field],color:palette[field]};
  delete t.fill;delete t.fillcolor;
 }
 // Independent paired fill traces cannot cover or join unrelated point curves.
 return [...shades,...series.filter(t=>t.meta?.axisRole==='interval'),...series.filter(t=>t.meta?.axisRole==='curve'&&!t.meta.main),...series.filter(t=>t.meta?.main)];
}
function prepareDistribution(key,el,layout){
 if(!el._distribution){
  el._distribution={mode:'auto',includeIntervals:false,window:0};document.querySelector('#'+key).classList.add('distribution-chart');
  const box=document.createElement('div');box.className='axis-settings';box.innerHTML=`<span class="axis-unit">Y-axis · ${key==='acceleration'?'pp':'%'}</span><button type="button" data-axis-auto>Auto Scale</button><label>Y-axis Min <input type="number" step="any" inputmode="decimal" aria-label="${key} Y-axis Min" data-axis-min></label><label>Y-axis Max <input type="number" step="any" inputmode="decimal" aria-label="${key} Y-axis Max" data-axis-max></label><button type="button" data-axis-reset>Reset</button><label class="axis-interval-option"><input type="checkbox" data-axis-intervals>自动范围包含预测区间</label><p class="axis-message" role="status"></p><button type="button" data-axis-full hidden>显示完整区间</button>`;
  el.before(box);el._axisBox=box;
  const reset=()=>{el._distribution.mode='auto';box.querySelectorAll('input[type=number]').forEach(i=>i.value='');syncDistribution(key,el);};
  box.querySelector('[data-axis-auto]').onclick=reset;box.querySelector('[data-axis-reset]').onclick=()=>{el._distribution.includeIntervals=false;box.querySelector('[data-axis-intervals]').checked=false;reset();};
  box.querySelector('[data-axis-intervals]').onchange=e=>{el._distribution.includeIntervals=e.target.checked;el._distribution.mode='auto';syncDistribution(key,el);};
  box.querySelector('[data-axis-full]').onclick=()=>{box.querySelector('[data-axis-intervals]').checked=true;el._distribution.includeIntervals=true;el._distribution.mode='auto';syncDistribution(key,el);};
  const manual=()=>{const min=box.querySelector('[data-axis-min]'),max=box.querySelector('[data-axis-max]');if(!validDistributionBounds(min.value,max.value)){box.querySelector('.axis-message').textContent='请输入有限数值，并确保Min小于Max；保留上一次有效范围。';return;}
   el._distribution.mode='manual';el._distribution.range=[Number(min.value),Number(max.value)];syncDistribution(key,el);};
  box.querySelectorAll('input[type=number]').forEach(i=>i.addEventListener('input',manual));
  const missing=document.createElement('p');missing.className='official-gap-note';missing.setAttribute('role','note');
  const months=HISTORY.groups[key].filter(r=>r.headline==null||r.core==null).map(r=>r.month);
  const future=Object.values(FORECAST.scenarios.base.groups[key]).filter(r=>r.headline==null||r.core==null).map(r=>r.month);
  missing.textContent='完整历史默认可见。3Y/5Y按图末月回溯36/60个月（含预测）。官方Headline/Core缺失月份：'+(months.join('、')||'无')+'。2025-10官方指数未公布，导致当月及2026-10同比/加速度为NA；不填0、不插值。'+(future.length?'预测Headline/Core的'+future.join('、')+'也因所需官方基期缺失保留NA。':'')+'历史末值为NA时，预测从首个有效预测月单独起画，不跨缺口连线。';
  box.after(missing);
  el._distributionRangeChange=async years=>{el._distribution.window=years;el._rangeChanging=true;try{await Plotly.relayout(el,{'xaxis.range':distributionWindow(el._displayRows,years),'xaxis.autorange':false});await syncDistribution(key,el);}finally{el._rangeChanging=false;}};
 }
 if(el._distribution.window!==null){layout.xaxis={...layout.xaxis,range:distributionWindow(el._displayRows,el._distribution.window),autorange:false};}
 document.querySelectorAll('#'+key+' [data-years]').forEach(b=>b.classList.toggle('active',el._distribution.window!==null&&Number(b.dataset.years)===el._distribution.window));
 layout.margin.b=innerWidth<600?140:100;layout.legend={...layout.legend,y:-.20,groupclick:'togglegroup',font:{size:10}};
 layout.yaxis={...layout.yaxis,autorange:false,zeroline:true,zerolinecolor:'#526b7b',zerolinewidth:1.5,title:{text:key==='acceleration'?'Percentage points (pp)':'Percent (%)'}};
}
async function syncDistribution(key,el){
 const s=el._distribution;if(!s)return;const dates=el.layout.xaxis.autorange?[null,null]:el.layout.xaxis.range||[null,null];
 const range=s.mode==='manual'?s.range:distributionRange(key,el.data,...dates,s.includeIntervals);
 const intervals=distributionExtent(el.data.filter(t=>t.meta?.axisRole==='interval'),...dates,true);
 const points=distributionExtent(el.data,...dates,false),cutBands=intervals&&(intervals.min<range[0]||intervals.max>range[1]);
 const cutPoints=points&&(points.min<range[0]||points.max>range[1]);
 let message=s.mode==='manual'?'Manual：使用指定范围。':'Auto：按当前时间范围和可见曲线缩放，保留10%空间。';
 if(key==='acceleration'&&range[0]>0||key==='acceleration'&&range[1]<0)message+=' 0 pp基准当前在范围外。';
 if(cutPoints)message+=' 注意：手动范围外仍有曲线数据，请扩大范围或Reset。';
 if(cutBands)message+=` 紫色预测区间部分在轴外（完整范围 ${intervals.min.toFixed(2)}至${intervals.max.toFixed(2)} ${key==='acceleration'?'pp':'%'}）；可显示完整区间。`;
 else if(!intervals)message+=' 预测区间阴影未显示；原始区间保留在悬停数值和下载中。';
 el._axisBox.querySelector('.axis-message').textContent=message;el._axisBox.querySelector('[data-axis-full]').hidden=!cutBands;
 el._axisBox.querySelector('[data-axis-auto]').classList.toggle('active',s.mode==='auto');
 if(JSON.stringify(el.layout.yaxis.range)!==JSON.stringify(range))await Plotly.relayout(el,{'yaxis.range':range,'yaxis.autorange':false});
}
function attachDistribution(key,el){
 if(!el._distributionEvents){el._distributionEvents=true;
  el.on('plotly_relayout',e=>{if(Object.keys(e).some(k=>k.startsWith('xaxis.'))){if(!el._rangeChanging&&!el._renderingDistribution)el._distribution.window=null;syncDistribution(key,el);}});
  el.on('plotly_restyle',()=>syncDistribution(key,el));
  el._distributionResize=new ResizeObserver(()=>{if(el.clientWidth&&(el.layout.width!==el.clientWidth||el.layout.height!==el.clientHeight))Plotly.relayout(el,{width:el.clientWidth,height:el.clientHeight,'margin.b':innerWidth<600?140:100});});el._distributionResize.observe(el);
 }
 return syncDistribution(key,el);
}
