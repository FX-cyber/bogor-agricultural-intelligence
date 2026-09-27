"""Metadata-first discovery using the documented BPS endpoints.

Unknown response shapes fail closed. No statistical observations are synthesized.
"""
import re
import unicodedata
from datetime import datetime, timezone
from app.services.bps_client import BPSError, walk

KEYWORDS = ('pertanian', 'hortikultura', 'tanaman', 'buah', 'sayuran',
            'luas panen', 'produktivitas', 'perkebunan', 'padi', 'palawija')


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).casefold().split())


def available_years(table):
    # Only explicit availability, never publication dates or invented intervals.
    value = table.get('ketersediaan_tahun', [])
    years = {int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b', str(value))}
    return sorted(years)


def score_table(table):
    text = normalize(' '.join(str(table.get(k, '')) for k in
                            ('judul', 'title', 'subject', 'bab', 'mms_subject')))
    if not any(k in text for k in KEYWORDS):
        return 0
    weights = {'produksi': 5, 'kecamatan': 5, 'sayuran': 4, 'buah': 4,
               'hortikultura': 3, 'tanaman': 2, 'bogor': 4, 'luas panen': 3}
    score = sum(w for k, w in weights.items() if k in text)
    score += min(5, len([y for y in available_years(table) if y >= 2021]))
    if table.get('unit') or table.get('satuan'):
        score += 2
    return max(1, score)


def verify_simdasi(payload, expected):
    # Documented wrapper uses wilayah for name and induk for the area code.
    regions = [n for n in walk(payload) if 'wilayah' in n and 'data' in n]
    if not regions:
        raise BPSError('SIMDASI', f'Wilayah {expected} could not be verified: region metadata absent.')
    for region in regions:
        name = normalize(region['wilayah'])
        if 'bogor' not in name or 'kota' in name:
            raise BPSError('SIMDASI', 'Returned region does not identify Kabupaten Bogor.')
        if region.get('induk') is not None and str(region['induk']) != expected:
            raise BPSError('SIMDASI', 'Returned wilayah identifier differs from expected code.')
    return True


class Discovery:
    def __init__(self, client, emit=print):
        self.client, self.emit = client, emit
        self.report = {'status': 'PARTIAL', 'bogor_domain_verified': False,
                       'simdasi_connected': False, 'candidates': [], 'errors': [], 'details': []}

    async def domains(self):
        s = self.client.settings
        for params, code, name in (({'type': 'prov'}, s.province, 'jawa barat'),
                                   ({'type': 'kabbyprov', 'prov': s.province}, s.domain, 'bogor')):
            records = []
            async for payload in self.client.pages('/v1/api/domain', params, 'BPS DOMAIN'):
                records.extend(walk(payload))
            match = next((r for r in records if str(r.get('domain_id')) == code
                          and name in normalize(r.get('domain_name', ''))
                          and 'kota' not in normalize(r.get('domain_name', ''))), None)
            if not match:
                raise BPSError('BPS DOMAIN', f'Expected domain {code} / {name} not found; stopping region discovery.')
            self.emit(f"[BPS] Verified: {match['domain_name']} [{code}]")
        self.report['bogor_domain_verified'] = True

    async def candidates(self, source, domain):
        if source == 'SIMDASI':
            searches = [('/v1/api/interoperabilitas/datasource/simdasi/id/23/',
                         {'wilayah': self.client.settings.wilayah})]
        elif source == 'statictable':
            searches = [('/v1/api/list/', {'model': source, 'domain': domain, 'lang': 'ind', 'keyword': k})
                        for k in ('produksi', 'pertanian', 'sayuran', 'buah', 'hortikultura')]
        else:
            searches = [('/v1/api/list', {'model': source, 'domain': domain})]
        result = {}
        for path, params in searches:
            try:
                async for payload in self.client.pages(path, params, source):
                    if source == 'SIMDASI':
                        verify_simdasi(payload, self.client.settings.wilayah)
                    for row in walk(payload):
                        table_id = row.get('id_tabel', row.get('table_id', row.get('id')))
                        title = row.get('judul', row.get('title'))
                        if table_id is None or not title or not score_table(row):
                            continue
                        result[str(table_id)] = {'id': str(table_id), 'title': title, 'source': source,
                            'domain': domain, 'score': score_table(row), 'years': available_years(row),
                            'metadata': row, 'requires_bogor_row_filter': domain == '3200'}
            except BPSError as exc:
                self.report['errors'].append(str(exc))
                self.emit(f'[BPS] {exc}')
        if source == 'SIMDASI' and result:
            self.report['simdasi_connected'] = True
        return sorted(result.values(), key=lambda t: (-t['score'], t['title']))

    async def fetch_details(self, table):
        source = table['source']
        if source == 'SIMDASI':
            years = [y for y in table['years'] if y >= 2021][-5:] or table['years'][-5:]
            if not years:
                self.emit('[DATA FETCH] No explicit available years; SIMDASI detail skipped.')
                return
        else:
            years = [None]  # Fetch metadata first; do not assume annual availability.
        for year in years:
            try:
                if source == 'SIMDASI':
                    path = '/v1/api/interoperabilitas/datasource/simdasi/id/25/'
                    params = {'wilayah': self.client.settings.wilayah, 'tahun': year, 'id_tabel': table['id']}
                else:
                    path = '/v1/view' if source == 'statictable' else '/v1/api/view'
                    params = {'model': source, 'domain': table['domain'], 'lang': 'ind', 'id': table['id']}
                try:
                    payload = await self.client.get(path, params, 'DATA FETCH')
                except BPSError as exc:
                    if source == 'statictable' and 'HTTP 404' in exc.reason:
                        payload = await self.client.get('/v1/api/view', params, 'STATIC DETAIL ALTERNATE')
                    else:
                        raise
                if source == 'SIMDASI':
                    verify_simdasi(payload, self.client.settings.wilayah)
                self.report['details'].append({'table_id': table['id'], 'year': year,
                    'source': source, 'domain': table['domain'], 'response': payload,
                    'normalization_status': 'AWAITING_SCHEMA_REVIEW'})
                self.emit(f"[DATA FETCH] Received {table['title']} / {year or 'metadata'}; raw response saved. Normalization unverified.")
            except BPSError as exc:
                self.report['errors'].append(str(exc))
                self.emit(str(exc))

    async def run(self):
        self.emit('[2] BPS DOMAIN')
        await self.domains()
        for source, domain in (('SIMDASI', '3201'), ('statictable', '3201'),
                               ('tablestatistic', '3201'), ('statictable', '3200'), ('tablestatistic', '3200')):
            self.emit(f'[TABLE DISCOVERY] Trying {source}, domain {domain}')
            tables = await self.candidates(source, domain)
            self.report['candidates'].extend(tables)
            self.emit(f'Agricultural candidates: {len(tables)}')
            for i, table in enumerate(tables[:10], 1):
                self.emit(f"{i}. {table['title']} | years: {table['years']} | score: {table['score']}")
            for table in tables[:3]:
                await self.fetch_details(table)
            # Continue fallbacks while normalization is not validated.
        self.report['checked_at'] = datetime.now(timezone.utc).isoformat()
        self.client.save('discovery', self.report)
        return self.report
