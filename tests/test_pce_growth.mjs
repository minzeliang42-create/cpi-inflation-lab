import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const ctx=vm.createContext({window:{addEventListener(){}},fmt:v=>v==null?'NA':v.toFixed(2),monthOffset:(m,n)=>{const d=new Date(m+'-01T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+n);return d.toISOString().slice(0,7);}});const source=fs.readFileSync('web/pce-growth.js','utf8');vm.runInContext(source,ctx);
assert.doesNotMatch(source,/diffusionComparison|diffusion-comparison|CPI vs PCE/);
assert.match(source,/originalPlot\.after\(box\)/);assert.match(source,/oneYear\.textContent='12M'/);assert.doesNotMatch(source,/forecast/i);assert.match(source,/range:\[0,100\]/);
console.log('Removed comparison text; PCE chart, placement, range controls and fixed axis preserved PASS');
