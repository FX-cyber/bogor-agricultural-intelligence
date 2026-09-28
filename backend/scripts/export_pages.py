"""Build public browser data from the reviewed snapshot; never access BPS/network."""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services.pipeline import read_dataset
from app.services.analytics import summarize, trends
from app.services.clustering import cluster
from app.services.attribution import source_url

snapshot = read_dataset(ROOT / 'backend/data/snapshot/normalized.json.gz')
fields = ['year', 'district_code', 'district', 'commodity', 'category', 'indicator', 'value', 'unit', 'geography_level']
sources, source_ids, rows = [], {}, []
for row in snapshot['rows']:
    key = (row['source_table_id'], row['year'])
    if key not in source_ids:
        source_ids[key] = len(sources)
        sources.append({k: row.get(k) for k in ('source', 'source_table_id', 'source_table_title', 'year', 'last_synced', 'last_updated')})
        sources[-1]['source_url'] = source_url(*key)
    rows.append([row.get(k) for k in fields] + [source_ids[key]])
options = {k: sorted({r[k] for r in snapshot['rows'] if r[k] is not None}) for k in ('year','district','commodity','category','unit','indicator')}
options['defaults'] = snapshot['default_filters']
# A district filter always leaves <6 districts; a commodity filter leaves <2
# valid cells per district. Only year/unit/category combinations can qualify.
clusters = {}
combinations = sorted({(r['year'], r['unit'], c) for r in snapshot['rows']
    if r['indicator'] == 'Produksi' and r['unit'] for c in ('', r['category'])})
for year, unit, category in combinations:
    filters = {'year': year, 'unit': unit, 'category': category}
    clusters[json.dumps([year, unit, category], separators=(',', ':'))] = cluster(snapshot['rows'], filters)
status = {k: snapshot.get(k) for k in ('last_sync','quality','bogor_domain_verified','simdasi_connected','data_source','discovery_errors','tables_discovered')}
status.update(api_connected=False, api_key_configured=False, domain='3201', wilayah='3201000',
    using_cache=True, stale=True, refreshing=False, error=None, tables_selected=len(snapshot['tables']))
tables = [{**{k:t[k] for k in ('id','title','source','domain','years','ingested_years','units','last_sync')}, 'source_url':source_url(t['id'])} for t in snapshot['tables']]
data = dict(version=1, fields=fields, rows=rows, sources=sources, options=options, status=status, tables=tables, clusters=clusters)
out = ROOT / 'frontend/public/data'
out.mkdir(parents=True, exist_ok=True)
payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
(out / 'snapshot.json.gz').write_bytes(gzip.compress(payload, mtime=0))
# Independent reference calculations for the browser regression suite; not shipped.
cases = [dict(year=y, unit=u, category=c) for y,u,c in combinations]
cases += [dict(year=2025, unit='kw', district=d) for d in options['district'][::7]]
cases += [dict(year=2025, unit='kw', commodity=c) for c in options['commodity'][::11]]
cases += [dict(year=2025), dict(year=2025,unit='kw',district='NO MATCH')]
references = [{'filters':f,'summary':summarize(snapshot['rows'],f),'trends':trends(snapshot['rows'],f)['series']} for f in cases]
test_dir = ROOT / '.local'
test_dir.mkdir(exist_ok=True)
(test_dir/'pages-reference.json').write_text(json.dumps(references,ensure_ascii=False,allow_nan=False),encoding='utf-8')
print(f'Exported {len(rows)} observations, {len(sources)} source-years, {len(clusters)} cluster combinations; {len(gzip.compress(payload))} bytes compressed.')
