import {unpack,analyze,explore,csv} from './static-analytics';
import type {Packed,Dataset} from './static-analytics';
const base=process.env.NEXT_PUBLIC_BASE_PATH||'';
let pending:Promise<Dataset>|undefined;
async function load():Promise<Dataset>{
  if(!pending)pending=(async()=>{
    const response=await fetch(`${base}/data/snapshot.json.gz`);
    if(!response.ok||!response.body)throw new Error('Snapshot belum dapat dimuat. Coba muat ulang halaman.');
    const stream=response.body.pipeThrough(new DecompressionStream('gzip'));
    return unpack(await new Response(stream).json() as Packed);
  })().catch(e=>{pending=undefined;throw e;});
  return pending;
}
export async function staticGet<T>(url:string,signal?:AbortSignal):Promise<T>{
  const data=await load();
  if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
  const [path,query]=url.split('?'),f=Object.fromEntries(new URLSearchParams(query));
  let result:unknown;
  if(path==='/api/bps/status')result=data.status;
  else if(path==='/api/agriculture/options')result=data.options;
  else if(path==='/api/bps/tables')result={selected:data.tables};
  else if(path==='/api/agriculture/dashboard')result=analyze(data,f);
  else if(path==='/api/agriculture/data'){const rows=explore(data,f),page=Math.max(1,Number(f.page)||1);result={rows:rows.slice((page-1)*25,page*25),total:rows.length};}
  else throw new Error('Halaman data tidak tersedia.');
  return result as T;
}
export async function downloadCsv(query:string){
  const data=await load(),rows=explore(data,Object.fromEntries(new URLSearchParams(query)));
  const url=URL.createObjectURL(new Blob([csv(rows)],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='bogor-agriculture.csv';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
