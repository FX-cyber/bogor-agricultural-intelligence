import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {unpack,analyze,explore,csv,matched} from '../lib/static-analytics.ts';

const data=unpack(JSON.parse(gunzipSync(readFileSync('frontend/public/data/snapshot.json.gz'))));
const references=JSON.parse(readFileSync('.local/pages-reference.json','utf8'));
const near=(a,b,label)=>{if(a==null||b==null)assert.equal(a,b,label);else assert.ok(Math.abs(a-b)<=1e-7*Math.max(1,Math.abs(b)),`${label}: ${a} != ${b}`);};
for(const {filters,summary,trends} of references){
  const result=analyze(data,filters);
  for(const key of ['total','observations','missing','active_commodities','district_count'])near(result.summary[key],summary[key],key);
  for(const key of ['change_percent','matched_observations','current','previous'])near(result.summary.yoy[key],summary.yoy[key],key);
  for(const key of ['top_commodities','top_districts']){
    assert.equal(result.summary[key].length,summary[key].length);
    const expected=new Map(summary[key].map(r=>[r.name,r.value]));
    for(const r of result.summary[key])near(r.value,expected.get(r.name),r.name);
  }
  assert.equal(result.trends.series.length,trends.length);
  result.trends.series.forEach((r,i)=>{assert.equal(r.year,trends[i].year);near(r.value,trends[i].value,'annual total');});
  for(const insight of result.insights)assert.ok(insight.provenance.length,'Insight must retain sources');
}
const rows=explore(data,{year:'2025',unit:'kw',search:'Cabai Rawit',sort:'value',direction:'asc'});
assert.ok(rows.length>0);
assert.ok(rows.every(r=>r.commodity==='Cabai Rawit'&&r.year===2025&&r.unit==='kw'));
assert.ok(csv(rows).includes('https://bogorkab.bps.go.id'));
assert.ok(csv(rows).includes('Layanan ini menggunakan API Badan Pusat Statistik (BPS).'));
assert.equal(explore(data,{search:'[.*'}).length,0,'search is literal');
assert.ok(csv([{...data.rows[0],commodity:'=1+1'}]).includes("'=1+1"));
assert.equal(matched([{...data.rows[0],year:2024,value:0},{...data.rows[0],year:2025,value:10}],2025).change_percent,null);
assert.equal(analyze(data,{year:'2025',unit:'kw',district:'Nanggung'}).clusters.available,false);
assert.equal(analyze(data,{year:'2025',unit:'kw',commodity:'Alpukat'}).clusters.available,false);
for(const cluster of Object.values(data.clusters))if(cluster.available){assert.ok(cluster.k>=2&&cluster.k<=6);assert.ok(cluster.silhouette>0);assert.ok(cluster.clusters.every(c=>c.districts.length>=2));}
console.log(`${references.length} Python/browser parity cases passed; filtering, CSV, missing values and cluster eligibility verified.`);
