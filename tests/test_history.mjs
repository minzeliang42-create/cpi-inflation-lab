import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const code=fs.readFileSync('web/history.js','utf8');const ctx=vm.createContext({window:{addEventListener(){}},fmt:v=>v==null?'NA':v.toFixed(2),stateNote:r=>r.data_status});vm.runInContext(code,ctx);
const rows=[{month:'2026-09',p10:1,p25:2,p50:3,p75:4,p90:5,headline:3.7,core:2.5,data_status:'official'},{month:'2026-10',p10:1,p25:2,p50:3,p75:4,p90:5,headline:null,core:null,data_status:'provisional'}];ctx.rows=rows;
assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(historicalWindow(rows,12))',ctx)),['2025-11-01','2026-10-31']);
assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(historicalWindow(rows))',ctx)),['2026-09-01','2026-10-31']);
const result=JSON.parse(vm.runInContext("JSON.stringify(historySeries('measures',rows))",ctx));const curves=result.filter(t=>!t.meta.shade);assert.equal(curves.length,7);assert.equal(result.filter(t=>t.meta.shade).length,6);assert.deepEqual(curves.find(t=>t.meta.field==='core').y,[2.5,null]);assert.ok(curves.every(t=>!t.line.dash&&t.connectgaps===false));
ctx.groups={acceleration:[{month:'2026-10',p50:-.2}],growth:[{month:'2026-10',items_pct:80,weight_pct:90}]};assert.match(vm.runInContext('breadthAnalysis(groups,null)',ctx),/NA/);
const html=fs.readFileSync('web/index.html','utf8');assert.doesNotMatch(html,/forecast\.js|distribution-axis\.js|FORECAST RESEARCH|HISTORY & FORECASTS/);assert.match(html,/Inflation Breadth/);
console.log('History windows, seven curves, retained NA, missing analysis and no forecast dependencies PASS');
