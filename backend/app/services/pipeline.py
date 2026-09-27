import asyncio
import json
from datetime import datetime, timezone
from app.config import get_settings
from app.services.bps_client import BPSClient, BPSError
from app.services.bps_discovery import Discovery
from app.services.normalizer import normalize_detail, validate_rows
from app.services.analytics import summarize, trends
from app.services.clustering import cluster
from app.services.insight_engine import insights


def now():
    return datetime.now(timezone.utc).isoformat()


def calculate(rows, filters):
    clusters = cluster(rows, filters)
    return {'summary': summarize(rows, filters), 'trends': trends(rows, filters),
            'clusters': clusters, 'insights': insights(rows, filters, clusters)}


class Pipeline:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.lock = asyncio.Lock()
        self.snapshot = None
        self.last_error = None
        self.last_attempt = None
        self.connected = False
        self.memo = {}
        path = self.settings.cache / 'normalized.json'
        if path.exists():
            try:
                value = json.loads(path.read_text(encoding='utf-8'))
                if value.get('schema_version') == 1 and value.get('rows'):
                    self.snapshot = value
            except (OSError, ValueError):
                self.last_error = 'Cached dataset could not be read. Run a refresh.'

    def status(self):
        snapshot = self.snapshot or {}
        stamp = snapshot.get('last_sync')
        stale = not stamp or (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds() >= 86400
        return {'api_connected': self.connected, 'api_key_configured': self.settings.configured,
                'bogor_domain_verified': snapshot.get('bogor_domain_verified', False),
                'simdasi_connected': snapshot.get('simdasi_connected', False),
                'domain': self.settings.domain, 'wilayah': self.settings.wilayah,
                'data_source': snapshot.get('data_source'), 'last_sync': stamp,
                'using_cache': bool(snapshot) and (not self.connected or bool(self.last_error) or stale),
                'stale': stale, 'refreshing': self.lock.locked(), 'last_attempt': self.last_attempt,
                'error': self.last_error, 'quality': snapshot.get('quality', {}),
                'discovery_errors': snapshot.get('discovery_errors', []),
                'tables_discovered': snapshot.get('tables_discovered', 0),
                'tables_selected': len(snapshot.get('tables', []))}

    async def refresh(self, use_cache=False, emit=print):
        async with self.lock:
            self.last_attempt = now()
            self.settings = get_settings()
            try:
                async with BPSClient(self.settings, use_cache=use_cache) as client:
                    discovery = Discovery(client, emit)
                    await discovery.domains()
                    all_tables, rows, selected, errors = [], [], [], []
                    quality = {'rows_rejected': 0, 'aggregate_rows_excluded': 0}
                    for source, domain in (('SIMDASI', '3201'), ('statictable', '3201'), ('tablestatistic', '3201'),
                                           ('statictable', '3200'), ('tablestatistic', '3200')):
                        emit(f'[BPS] Trying {source} / {domain}')
                        tables = await discovery.candidates(source, domain)
                        all_tables.extend(tables)
                        for table in tables:
                            title = table['title'].lower()
                            if not any(k in title for k in ('produksi', 'luas panen', 'produktivitas')):
                                continue
                            if domain == '3201' and source == 'SIMDASI' and 'kecamatan' not in title:
                                continue
                            emit(f"[BPS] Candidate: {table['title']} | years: {table['years']}")
                            start = len(discovery.report['details'])
                            await discovery.fetch_details(table)
                            table_rows = []
                            for detail in discovery.report['details'][start:]:
                                try:
                                    normalized, diagnostics = normalize_detail(detail['response'], table, self.last_attempt)
                                    table_rows.extend(normalized)
                                    for key, count in diagnostics.items():
                                        quality[key] += count
                                except BPSError as exc:
                                    errors.append(str(exc))
                            if table_rows:
                                table['units'] = sorted({r['unit'] for r in table_rows if r['unit']})
                                table['ingested_years'] = sorted({r['year'] for r in table_rows})
                                table['last_sync'] = self.last_attempt
                                selected.append(table)
                                rows.extend(table_rows)
                        if any(r['indicator'] == 'Produksi' and r['value'] == r['value'] for r in rows):
                            break
                    sync_stamp = min(client.fetched_times) if client.fetched_times else self.last_attempt
                    for row in rows:
                        row['last_synced'] = sync_stamp
                    for table in selected:
                        table['last_sync'] = sync_stamp
                    normalized, validated = validate_rows(rows)
                    if self.snapshot and (discovery.report['errors'] or errors):
                        raise BPSError('REFRESH', 'Some table requests or adapters failed; previous valid dataset preserved. ' +
                                       '; '.join((discovery.report['errors'] + errors)[:3]))
                    quality.update(validated)
                    emit(f"[NORMALIZATION] {quality['numeric_rows']} numeric / {quality['rows_normalized']} rows; {quality['districts']} regions")
                    units = sorted({r['unit'] for r in normalized if r['indicator'] == 'Produksi' and r['unit']})
                    default = {'year': max(r['year'] for r in normalized), 'unit': 'kw' if 'kw' in units else units[0] if units else ''}
                    emit('[ANALYTICS] Computing statistics, K-Means and insights')
                    calculated = await asyncio.to_thread(calculate, normalized, default)
                    snapshot = {'schema_version': 1, 'rows': normalized, 'tables': selected,
                        'candidates': all_tables, 'quality': quality, 'last_sync': sync_stamp,
                        'bogor_domain_verified': True, 'simdasi_connected': discovery.report['simdasi_connected'],
                        'data_source': selected[0]['source'], 'default_filters': default,
                        'discovery_errors': discovery.report['errors'] + errors,
                        'tables_discovered': len(all_tables), 'computed': calculated}
                    client.save('normalized', snapshot)
                    self.snapshot, self.connected, self.last_error = snapshot, client.network_successes > 0, None
                    self.memo.clear()
                    emit('STATUS: READY' if not snapshot['discovery_errors'] else 'STATUS: PARTIAL (usable data; see discovery errors)')
                    return self.status()
            except (BPSError, ValueError, OSError) as exc:
                self.connected = False
                self.last_error = str(exc) if isinstance(exc, BPSError) else 'Processing/cache failure; previous valid dataset preserved.'
                emit(f'[PIPELINE] {self.last_error}')
                if not self.snapshot:
                    raise BPSError('PIPELINE', self.last_error) from None
                return self.status()

    def analyze(self, filters):
        rows = (self.snapshot or {}).get('rows', [])
        key = json.dumps(filters, sort_keys=True)
        if key not in self.memo:
            if len(self.memo) >= 64:
                self.memo.clear()
            self.memo[key] = calculate(rows, filters)
        return self.memo[key]
