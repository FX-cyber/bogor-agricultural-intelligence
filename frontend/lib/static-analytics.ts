import type {Observation, Source, Filters, Summary, Insight, Cluster, Options, Status, TableSource} from './types';
export type Row = Observation & {geography_level:string};
export type Dataset = {rows:Row[]; options:Options; status:Status; tables:TableSource[]; clusters:Record<string,Cluster>};
export type Packed = Omit<Dataset,'rows'> & {version:number; fields:string[]; sources:Source[]; rows:unknown[][]};
export function unpack(p:Packed):Dataset {
  if(p.version!==1 || !Array.isArray(p.rows)) throw new Error('Format snapshot tidak didukung.');
  return {...p,rows:p.rows.map(values=>({...p.sources[values[p.fields.length] as number],...Object.fromEntries(p.fields.map((k,i)=>[k,values[i]]))}) as Row)};
}
const sum=(a:number[])=>a.reduce((s,v)=>s+v,0);
const valid=(r:Row)=>r.value!==null && Number.isFinite(r.value);
const unique=<T,>(a:T[])=>[...new Set(a)];
const group=<T,>(a:T[],key:(r:T)=>string)=>{const m=new Map<string,T[]>();for(const r of a){const k=key(r);if(!m.has(k))m.set(k,[]);m.get(k)!.push(r);}return m;};
export function filtered(rows:Row[],f:Filters,includeYear=true) {
  return rows.filter(r=>(['year','district','commodity','category','unit','indicator'] as const).every(k=>!f[k]||(!includeYear&&k==='year')||String(r[k])===String(f[k])));
}
function production(rows:Row[],f:Filters) {
  let a=filtered(rows,{...f,indicator:'Produksi'},false);
  if(a.some(r=>r.geography_level==='kecamatan'))a=a.filter(r=>r.geography_level==='kecamatan');
  const units=unique(a.flatMap(r=>r.unit?[r.unit]:[])).sort();
  const unit=f.unit || (units.length===1?units[0]:null);
  return {rows:unit?a.filter(r=>r.unit===unit):[],unit,units};
}
export function provenance(rows:Row[]):Source[] {
  const m=new Map<string,Source>();for(const r of rows){const s:Source={source:r.source,source_table_id:r.source_table_id,source_table_title:r.source_table_title,year:r.year,last_synced:r.last_synced,last_updated:r.last_updated,source_url:r.source_url};m.set(JSON.stringify(s),s);}return [...m.values()];
}
const identity=(r:Row)=>JSON.stringify([r.district_code,r.commodity,r.category,r.unit]);
export function matched(rows:Row[],year:number) {
  const current=rows.filter(r=>r.year===year&&valid(r)), previous=rows.filter(r=>r.year===year-1&&valid(r));
  const old=new Map(previous.map(r=>[identity(r),r.value!]));
  const pairs=current.filter(r=>old.has(identity(r)));
  const a=pairs.length?sum(pairs.map(r=>r.value!)):null,b=pairs.length?sum(pairs.map(r=>old.get(identity(r))!)):null;
  return {current:a,previous:b,change_percent:a!==null&&b!==null&&b>0?(a-b)/b*100:null,matched_observations:pairs.length,current_observations:current.length,previous_observations:previous.length};
}
function rank(rows:Row[],key:'district'|'commodity') {
  return [...group(rows.filter(valid),r=>r[key])].map(([name,a])=>({name,value:sum(a.map(r=>r.value!))})).sort((a,b)=>b.value-a.value||a.name.localeCompare(b.name));
}
export function summarize(rows:Row[],f:Filters):Summary {
  const p=production(rows,f),year=Number(f.year||Math.max(...p.rows.map(r=>r.year))),current=p.rows.filter(r=>r.year===year),v=current.filter(valid);
  return {year,unit:p.unit,total:v.length?sum(v.map(r=>r.value!)):null,yoy:matched(p.rows,year),active_commodities:unique(v.filter(r=>r.value!>0).map(r=>r.commodity)).length,district_count:unique(v.filter(r=>r.geography_level==='kecamatan').map(r=>r.district)).length,observations:current.length,missing:current.length-v.length,top_commodities:rank(current,'commodity'),top_districts:rank(current.filter(r=>r.geography_level==='kecamatan'),'district'),provenance:provenance(current),message:p.units.length>1&&!p.unit?'Pilih satu satuan untuk analisis.':null};
}
export function trends(rows:Row[],f:Filters) {
  const p=production(rows,f);
  const series=[...group(p.rows,r=>String(r.year))].map(([year,a])=>({year:Number(year),value:a.some(valid)?sum(a.filter(valid).map(r=>r.value!)):null})).sort((a,b)=>a.year-b.year);
  const commodity_trends=[];
  for(const [commodity,a] of group(p.rows,r=>r.commodity)) {
    const years=unique(a.filter(valid).map(r=>r.year)).sort((a,b)=>a-b);
    if(years.length<3)continue;
    const districts=[...group(a,r=>r.district_code).values()].map(rs=>new Map(rs.filter(valid).map(r=>[r.year,r.value!]))).filter(m=>years.every(y=>m.has(y)));
    if(!districts.length)continue;
    const values=years.map(y=>sum(districts.map(m=>m.get(y)!))),mean=sum(values)/years.length;
    if(mean<=0)continue;
    const xm=sum(years)/years.length,slope=sum(years.map((x,i)=>(x-xm)*(values[i]-mean)))/sum(years.map(x=>(x-xm)**2));
    const relative_slope=slope/mean,cv=Math.sqrt(sum(values.map(v=>(v-mean)**2))/(values.length-1))/mean;
    commodity_trends.push({commodity,slope,relative_slope,classification:relative_slope>.02?'Increasing':relative_slope<-.02?'Decreasing':'Stable',observations:years.length,districts:districts.length,cv,unit:p.unit,provenance:provenance(a)});
  }
  return {series,unit:p.unit??'',commodity_trends,note:'Total observasi tersedia. Tren/CV memakai panel kecamatan lengkap (≥3 tahun).'};
}
export function clusterResult(data:Dataset,f:Filters):Cluster {
  const p=production(data.rows,f),year=Number(f.year||Math.max(...p.rows.map(r=>r.year)));
  const current=p.rows.filter(r=>r.year===year&&r.geography_level==='kecamatan');
  const eligible=[...group(current,r=>r.district).values()].filter(a=>a.filter(valid).length>=2&&a.filter(valid).length/a.length>=.6).length;
  if(!f.district&&!f.commodity){const c=data.clusters[JSON.stringify([year,p.unit,f.category||''])];if(c)return c;}
  return {available:false,eligible_districts:eligible,unit:p.unit??'',message:'Data belum mencukupi untuk analisis cluster yang reliabel.'};
}
export function analyze(data:Dataset,f:Filters) {
  const summary=summarize(data.rows,f),history=trends(data.rows,f),clusters=clusterResult(data,f),p=production(data.rows,f),year=summary.year,total=summary.total;
  const insights:Insight[]=[];
  const add=(type:string,severity:string,title:string,message:string,evidence:Record<string,unknown>,priority:number,sources=summary.provenance)=>insights.push({type,severity,title,message,evidence,priority,provenance:sources});
  if(total!==null) {
    const leader=summary.top_commodities[0],top=summary.top_districts[0];
    if(leader&&total>0){const share=leader.value/total*100;add('leader','positive','Komoditas dengan produksi terbesar',`${leader.name} menyumbang ${share.toFixed(1)}% dari produksi tercatat pada ${year} (${p.unit}).`,{commodity:leader.name,production:leader.value,total,share_percent:share},75);if(share>=40)add('concentration','neutral','Produksi terkonsentrasi',`${share.toFixed(1)}% volume tercatat berasal dari satu komoditas; bukan ukuran nilai ekonomi.`,{commodity:leader.name,share_percent:share},78);}
    if(top)add('leader','positive','Sentra produksi tercatat',`${top.name} memiliki produksi tercatat tertinggi pada ${year}: ${top.value.toLocaleString('id-ID')} ${p.unit}.`,top,70);
    const changes=[...group(p.rows,r=>r.commodity)].map(([name,rows])=>({name,rows,change:matched(rows,year)})).filter(v=>v.change.change_percent!==null);
    const threshold=sum(changes.map(v=>v.change.previous??0))*.01;
    const eligible=changes.filter(({change:c})=>c.previous!>0&&c.previous!>=threshold&&c.matched_observations>=.8*Math.max(c.current_observations,c.previous_observations));
    for(const sign of [1,-1]){const v=eligible.filter(v=>sign*v.change.change_percent!>=5).sort((a,b)=>sign*(b.change.change_percent!-a.change.change_percent!))[0];if(v)add(sign===1?'growth':'decline',sign===1?'positive':'warning',sign===1?'Pertumbuhan persentase tertinggi':'Penurunan produksi terbesar',`${v.name} ${sign===1?'meningkat':'turun'} ${Math.abs(v.change.change_percent!).toFixed(1)}% pada ${year} dibanding ${year-1}, pada kecamatan dengan data di kedua tahun.`,{...v.change,minimum_base:threshold,unit:p.unit},85+Math.min(10,Math.abs(v.change.change_percent!)/10),provenance(v.rows));}
    if(history.commodity_trends.length){const t=[...history.commodity_trends].sort((a,b)=>Math.abs(b.relative_slope)-Math.abs(a.relative_slope))[0];const {provenance:s,...e}=t;add('trend','neutral','Arah perubahan antar tahun',`${t.commodity}: ${t.classification}, berdasarkan ${t.observations} tahun pada ${t.districts} kecamatan dengan data lengkap.`,e,60,s);const v=[...history.commodity_trends].sort((a,b)=>b.cv-a.cv)[0];if(v.cv>=.3){const {provenance:s,...e}=v;add('volatility','warning','Variasi produksi tinggi',`${v.commodity} menunjukkan variasi relatif tertinggi pada panel lengkap (CV ${v.cv.toFixed(2)}).`,e,80,s);}}
    if(summary.missing)add('data_quality','warning','Cakupan data perlu diperhatikan',`${summary.missing} dari ${summary.observations} observasi tidak memiliki nilai. Total dan peringkat hanya mencakup nilai tersedia.`,{missing:summary.missing,observations:summary.observations},100);
    if(clusters.available)add('cluster','neutral','Pola produksi kecamatan',`K-Means menemukan ${clusters.k} kelompok pada ${clusters.points?.length} kecamatan yang memenuhi cakupan minimum.`,{silhouette:clusters.silhouette,k:clusters.k,features:clusters.features},65);
  }
  return {summary,trends:history,clusters,insights:insights.sort((a,b)=>b.priority-a.priority).slice(0,6)};
}
export function explore(data:Dataset,f:Filters) {
  let rows=filtered(data.rows,f);
  if(f.search){const q=f.search.toLocaleLowerCase();rows=rows.filter(r=>[r.district,r.commodity,r.source_table_title].some(s=>s.toLocaleLowerCase().includes(q)));}
  const key=(['year','district','commodity','indicator','value','unit','category'].includes(f.sort)?f.sort:'year') as keyof Row;
  const direction=f.direction==='asc'?1:-1;
  return [...rows].sort((a,b)=>a[key]==null?(b[key]==null?0:1):b[key]==null?-1:direction*(typeof a[key]==='number'?Number(a[key])-Number(b[key]):String(a[key]).localeCompare(String(b[key]))));
}
export function csv(rows:Row[]) {
  const keys=['year','district_code','district','commodity','category','indicator','value','unit','source','source_table_id','source_table_title','source_url','last_synced','last_updated','geography_level'] as const;
  const escape=(v:unknown)=>{let s=v==null?'':String(v);if(typeof v==='string'&&/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
  return '\uFEFF'+[keys.join(',')+',api_notice,processing_note',...rows.map(r=>[...keys.map(k=>r[k]),'Layanan ini menggunakan API Badan Pusat Statistik (BPS).','Data BPS diolah aplikasi independen; bukan analisis resmi BPS.'].map(escape).join(','))].join('\r\n');
}
