"""Normalize observed SIMDASI contracts; unknown schemas are rejected, not guessed."""
import html
import json
import math
import re
import pandas as pd
from app.services.bps_client import BPSError, walk

FIELDS = ['year', 'district_code', 'district', 'commodity', 'category', 'indicator',
          'value', 'unit', 'source', 'source_table_id', 'source_table_title', 'last_updated',
          'last_synced', 'geography_level', 'metadata']
IDENTITY = ['year', 'district_code', 'commodity', 'category', 'indicator', 'unit', 'geography_level']


def clean_text(value):
    return ' '.join(re.sub(r'<[^>]*>', '', html.unescape(html.unescape(str(value or '')))).split())


def parse_number(value, zero_symbols=()):
    if value is None or isinstance(value, bool):
        return float('nan')
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else float('nan')
    text = clean_text(value).replace('\u00a0', '')
    if text in zero_symbols:
        return 0.0
    if text.casefold() in ('', '-', '–', '...', 'na', 'n/a', 'null'):
        return float('nan')
    # This adapter reads Indonesian formatted BPS display values. A period is a
    # grouping separator only with valid three-digit groups, never removed blindly.
    if re.fullmatch(r'[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?', text):
        return float(text.replace('.', '').replace(',', '.'))
    if re.fullmatch(r'[+-]?\d+(?:,\d+)?', text):
        return float(text.replace(',', '.'))
    if re.fullmatch(r'[+-]?\d+\.\d{1,2}', text):
        return float(text)
    return float('nan')


def district_name(value):
    return re.sub(r'^kecamatan\s+', '', clean_text(value), flags=re.I).title()


def normalize_detail(detail, table, synced):
    bodies = [n for n in walk(detail) if isinstance(n.get('kolom'), dict)
              and isinstance(n.get('data'), list) and 'tahun_data' in n]
    if not bodies:
        if any(isinstance(n.get('table'), str) for n in walk(detail)):
            from app.services.bps_legacy import normalize_static
            return normalize_static(detail, table, synced)
        raise BPSError('NORMALIZATION', 'Unsupported detail schema; raw response retained for inspection.')
    rows, rejected, aggregates = [], 0, 0
    for body in bodies:
        region = clean_text(body.get('wilayah')).lower()
        provincial = table['domain'] == '3200'
        if not provincial and ('bogor' not in region or 'kota' in region):
            raise BPSError('NORMALIZATION', 'Response geography is not Kabupaten Bogor.')
        year = body['tahun_data']
        if not str(year).isdigit() or not 1900 <= int(year) <= 2100:
            raise BPSError('NORMALIZATION', 'Invalid reference year.')
        title = clean_text(table['title']).lower()
        category = ('Tanaman tahunan' if 'tahunan' in title else 'Tanaman semusim' if
                    'semusim' in title else 'Biofarmaka' if 'biofarmaka' in title else
                    'Tanaman hias' if 'hias' in title else 'Perkebunan' if 'perkebunan' in title
                    else clean_text(body.get('subject')) or 'Tidak terklasifikasi')
        symbols = body.get('keterangan_data', {})
        zeros = [k for k, v in symbols.items() if 'nol' in clean_text(v).lower()]
        for row in body['data']:
            code = str(row.get('kode_wilayah', ''))
            name = district_name(row.get('label_raw') or row.get('label'))
            if provincial:
                if code not in ('3201', '3201000') and name.lower() != 'kabupaten bogor':
                    aggregates += 1
                    continue
                level, name, code = 'kabupaten', 'Kabupaten Bogor', '3201'
            else:
                if code in ('3201', '3201000') or name.lower() in ('bogor', 'kabupaten bogor', 'jumlah', 'total'):
                    aggregates += 1
                    continue
                if not re.fullmatch(r'3201\d{3}', code) or not name:
                    rejected += 1
                    continue
                level = 'kecamatan'
            for key, cell in row.get('variables', {}).items():
                column = body['kolom'].get(key, {})
                label = clean_text(column.get('nama_variabel'))
                match = re.match(r'^(Produksi|Luas Panen|Luas Areal|Produktivitas)\s+(.+?)(?:\s*\(([^()]*)\))?$', label, re.I)
                if not match:
                    rejected += 1
                    continue
                indicator, commodity, label_unit = match.groups()
                unit = clean_text(column.get('satuan')) or label_unit or None
                # Unit codes can omit scale: observed plantation label is "ribu ton"
                # while its satuan code is "ton". Never drop the label's multiplier.
                if label_unit and re.match(r'^(ribu|juta|miliar)\s', label_unit, re.I):
                    unit = label_unit.lower()
                raw = cell.get('value_raw')
                if raw is None:
                    raw = cell.get('value')
                number = parse_number(raw, zeros)
                if not math.isnan(number) and number < 0:
                    rejected += 1
                    continue
                rows.append(dict(year=int(year), district_code=code, district=name,
                    commodity=commodity.strip(), category=category, indicator=indicator.title(),
                    value=number, unit=unit, source=('BPS Provinsi Jawa Barat — filtered for Kabupaten Bogor'
                      if provincial else 'BPS Kabupaten Bogor'), source_table_id=table['id'],
                    source_table_title=clean_text(body.get('judul_tabel') or table['title']),
                    last_updated=table['metadata'].get('latest_update') or body.get('table_created'),
                    last_synced=synced, geography_level=level,
                    metadata={'original_district': row.get('label'), 'raw_value': raw,
                              'value_code': cell.get('value_code'), 'column': column,
                              'notes': body.get('catatan'), 'symbols': symbols, 'source': body.get('sumber')}))
    return rows, {'rows_rejected': rejected, 'aggregate_rows_excluded': aggregates}


def validate_rows(rows):
    frame = pd.DataFrame(rows, columns=FIELDS)
    if frame.empty:
        raise BPSError('VALIDATION', 'No supported agricultural observations normalized.')
    frame['value'] = pd.to_numeric(frame.value, errors='coerce')
    labels = frame.sort_values('year', ascending=False).drop_duplicates('commodity')
    canonical = {}
    for name in labels.commodity:
        canonical.setdefault(name.casefold(), name)
    frame['commodity'] = frame.commodity.map(lambda name: canonical[name.casefold()])
    duplicate_count = int(frame.duplicated(IDENTITY).sum())
    conflicts = frame.groupby(IDENTITY, dropna=False).value.nunique(dropna=False)
    if (conflicts > 1).any():
        raise BPSError('VALIDATION', 'Conflicting duplicate observations; preserving previous valid cache.')
    frame = frame.drop_duplicates(IDENTITY)
    names = frame.groupby('district_code').district.nunique()
    if (names > 1).any():
        raise BPSError('VALIDATION', 'Inconsistent district names for a region code.')
    report = {'rows_normalized': len(frame), 'numeric_rows': int(frame.value.notna().sum()),
              'missing_values': int(frame.value.isna().sum()), 'duplicates_removed': duplicate_count,
              'unknown_units': int(frame.unit.isna().sum()), 'districts': int(frame.district.nunique()),
              'years': sorted(frame.year.unique().tolist())}
    # pandas serializes NaN as JSON null; never emit non-standard NaN API values.
    return json.loads(frame.to_json(orient='records', force_ascii=False)), report
