'use strict';
// Presentation only. No transformation of x, y, customdata, or data downloads.
function distributionExtent(series,start,end,includeIntervals=false){
 const lo=start?String(start).slice(0,7):'',hi=end?String(end).slice(0,7):'9999-12';let min=Infinity,max=-Infinity,count=0;
 for(const t of series){if(t.visible===false||t.visible==='legendonly'||(!includeIntervals&&t.meta?.axisRole==='interval'))continue;
  for(let i=0;i<(t.y?.length||0);i++){const m=String(t.x[i]).slice(0,7),v=t.y[i];if(m>=lo&&m<=hi&&typeof v==='number'&&Number.isFinite(v)){min=Math.min(min,v);max=Math.max(max,v);count++;}}}
 return count?{min,max,count}:null;
}
function distributionRange(key,series,start,end,includeIntervals=false){
 const extent=distributionExtent(series,start,end,includeIntervals);if(!extent)return key==='acceleration'?[-1,1]:[0,1];
 let {min,max}=extent;if(key==='acceleration'){min=Math.min(0,min);max=Math.max(0,max);}
 const pad=Math.max(max-min,.5)*.1;return [min-pad,max+pad];
}
function validDistributionBounds(min,max){return String(min).trim()!==''&&String(max).trim()!==''&&Number.isFinite(Number(min))&&Number.isFinite(Number(max))&&Number(min)<Number(max);}
function decorateDistribution(key,series){
 const fields=['p10','p25','p75','p90','p50','headline','core'];
 const palette={p10:'rgba(91,137,167,.65)',p25:'rgba(91,137,167,.75)',p75:'rgba(91,137,167,.75)',p90:'rgba(91,137,167,.65)',p50:'#173d55',headline:'#ac751b',core:'#b44756'};
 for(const t of series){const interval=t.uid.includes('-lower')||t.uid.includes('-upper');if(interval){t.meta={axisRole:'interval'};continue;}
  const field=t.uid.includes('-history-')?fields[Number(t.uid.split('-').at(-1))]:t.uid.split('-').at(-1);
  const main=['p50','headline','core'].includes(field);t.meta={axisRole:'curve',field,main};t.legendgroup=key+'-'+field;
  t.line={...t.line,color:palette[field],width:main?(field==='p50'?3.4:3):1.15};
  t.name=({p50:'Median',headline:'Headline',core:'Core'}[field]||field.toUpperCase())+(t.uid.includes('-forecast-')?' · Forecast':'');
  t.showlegend=!t.uid.includes('-forecast-');
  if(main){t.mode='lines+markers';t.marker={size:field==='core'?4:3.5,symbol:field==='core'?'diamond':field==='headline'?'square':'circle',color:palette[field]};}
  if(t.fill)t.fillcolor=field==='p75'?'rgba(93,147,180,.19)':'rgba(168,201,220,.12)';
 }
 // Keep fill chains intact; draw key lines last so shading cannot cover them.
 return [...series.filter(t=>!t.meta?.main),...series.filter(t=>t.meta?.main)];
}
function prepareDistribution(key,el,layout){
 if(!el._distribution){
  el._distribution={mode:'auto',includeIntervals:false};document.querySelector('#'+key).classList.add('distribution-chart');
  const box=document.createElement('div');box.className='axis-settings';box.innerHTML=`<span class="axis-unit">Y-axis · ${key==='acceleration'?'pp':'%'}</span><button type="button" data-axis-auto>Auto Scale</button><label>Y-axis Min <input type="number" step="any" inputmode="decimal" aria-label="${key} Y-axis Min" data-axis-min></label><label>Y-axis Max <input type="number" step="any" inputmode="decimal" aria-label="${key} Y-axis Max" data-axis-max></label><button type="button" data-axis-reset>Reset</button><label class="axis-interval-option"><input type="checkbox" data-axis-intervals>自动范围包含预测区间</label><p class="axis-message" role="status"></p><button type="button" data-axis-full hidden>显示完整区间</button>`;
  el.before(box);el._axisBox=box;
  const reset=()=>{el._distribution.mode='auto';box.querySelectorAll('input[type=number]').forEach(i=>i.value='');syncDistribution(key,el);};
  box.querySelector('[data-axis-auto]').onclick=reset;box.querySelector('[data-axis-reset]').onclick=()=>{el._distribution.includeIntervals=false;box.querySelector('[data-axis-intervals]').checked=false;reset();};
  box.querySelector('[data-axis-intervals]').onchange=e=>{el._distribution.includeIntervals=e.target.checked;el._distribution.mode='auto';syncDistribution(key,el);};
  box.querySelector('[data-axis-full]').onclick=()=>{box.querySelector('[data-axis-intervals]').checked=true;el._distribution.includeIntervals=true;el._distribution.mode='auto';syncDistribution(key,el);};
  const manual=()=>{const min=box.querySelector('[data-axis-min]'),max=box.querySelector('[data-axis-max]');if(!validDistributionBounds(min.value,max.value)){box.querySelector('.axis-message').textContent='请输入有限数值，并确保Min小于Max；保留上一次有效范围。';return;}
   el._distribution.mode='manual';el._distribution.range=[Number(min.value),Number(max.value)];syncDistribution(key,el);};
  box.querySelectorAll('input[type=number]').forEach(i=>i.addEventListener('input',manual));
  const end=FORECAST.meta.forecast_end+'-28',date=new Date(end);date.setUTCFullYear(date.getUTCFullYear()-3);
  layout.xaxis={...layout.xaxis,range:[date.toISOString().slice(0,10),end],autorange:false};
  document.querySelectorAll('#'+key+' [data-years]').forEach(b=>b.classList.toggle('active',b.dataset.years==='3'));
 }
 layout.margin.b=innerWidth<600?140:100;layout.legend={...layout.legend,y:-.20,groupclick:'togglegroup',font:{size:10}};
 layout.yaxis={...layout.yaxis,autorange:false,zeroline:true,zerolinecolor:'#526b7b',zerolinewidth:1.5,title:{text:key==='acceleration'?'Percentage points (pp)':'Percent (%)'}};
}
async function syncDistribution(key,el){
 const s=el._distribution;if(!s)return;const dates=el.layout.xaxis.autorange?[]:el.layout.xaxis.range||[];
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
  el.on('plotly_relayout',e=>{if(Object.keys(e).some(k=>k.startsWith('xaxis.')))syncDistribution(key,el);});
  el.on('plotly_restyle',()=>syncDistribution(key,el));
  el._distributionResize=new ResizeObserver(()=>{if(el.clientWidth&&(el.layout.width!==el.clientWidth||el.layout.height!==el.clientHeight))Plotly.relayout(el,{width:el.clientWidth,height:el.clientHeight,'margin.b':innerWidth<600?140:100});});el._distributionResize.observe(el);
 }
 return syncDistribution(key,el);
}
