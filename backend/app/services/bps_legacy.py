"""HTML adapters for layouts inspected in live BPS static-table responses.

Only explicit annual totals or province tables with an unambiguous Kabupaten
Bogor row are accepted. Monthly cells and Kota Bogor never enter annual totals.
"""
import html
import re
from lxml import html as lxml_html
from app.services.bps_client import BPSError, walk


def html_grid(markup):
    root = lxml_html.fromstring(html.unescape(markup))
    grid, spans = [], {}
    for row_index, row in enumerate(root.xpath('//table[not(ancestor::table)]/tr|//table[not(ancestor::table)]/tbody/tr')):
        values = {}
        for (r, c), value in list(spans.items()):
            if r == row_index:
                values[c] = value
        column = 0
        for cell in row.xpath('./td|./th'):
            while column in values:
                column += 1
            text = ' '.join(' '.join(cell.itertext()).split())
            width, height = int(cell.get('colspan', '1')), int(cell.get('rowspan', '1'))
            if width > 100 or height > 100:
                raise BPSError('STATIC PARSER', 'Unexpected HTML span dimensions.')
            for x in range(width):
                values[column + x] = text
                for y in range(1, height):
                    spans[row_index + y, column + x] = text
            column += width
        grid.append([values.get(i, '') for i in range(max(values, default=-1) + 1)])
    return grid


def normalize_static(payload, table, synced):
    from app.services.normalizer import clean_text, parse_number
    body = next((n for n in walk(payload) if isinstance(n.get('table'), str)), None)
    if not body:
        raise BPSError('STATIC PARSER', 'No supported HTML table found.')
    title = clean_text(body.get('title') or table['title'])
    years = sorted(set(re.findall(r'\b(?:19|20)\d{2}\b', title)))
    if len(years) != 1 or 'produksi' not in title.lower():
        raise BPSError('STATIC PARSER', 'Requires explicit single reference year and production indicator.')
    rows = []

    def record(commodity, unit, value):
        rows.append(dict(year=int(years[0]), district_code='3201', district='Kabupaten Bogor',
            commodity=commodity, category='Tanaman semusim' if 'semusim' in title.lower() else 'Sayuran',
            indicator='Produksi', value=parse_number(value), unit=unit, geography_level='kabupaten',
            source='BPS Provinsi Jawa Barat — filtered for Kabupaten Bogor' if table['domain']=='3200' else 'BPS Kabupaten Bogor',
            source_table_id=table['id'],source_table_title=title,last_synced=synced,
            last_updated=body.get('updt_date'),metadata={'raw_value':value,'layout':'static HTML annual',
                'original_district':'Kabupaten Bogor','source_metadata':{k:v for k,v in body.items() if k!='table'}}))

    grid = html_grid(body['table'])
    if table['domain'] == '3200':
        header = next((r for r in grid if any(v.lower() == 'kabupaten/kota' for v in r)), None)
        if not header:
            raise BPSError('STATIC PARSER', 'Province geographic header could not be identified.')
        columns = {}
        for i, text in enumerate(header):
            match = re.fullmatch(r'(.+?)\s*\(([^()]+)\)', text)
            if match:
                name, unit = match.groups()
                unit = 'kw' if unit.lower() in ('kwintal','kuintal') else unit.lower()
                columns[i] = (name.strip(), unit)
        section = None
        for row in grid:
            meaningful = {v.lower() for v in row if v}
            if any(re.fullmatch(r'kabupaten(?:\s*/\s*regency)?', v) for v in meaningful):
                section = 'kabupaten'
            elif any(re.fullmatch(r'kota(?:\s*/\s*city)?', v) for v in meaningful):
                section = 'kota'
            if section == 'kabupaten' and ('bogor' in meaningful or 'kabupaten bogor' in meaningful):
                for i, (commodity, unit) in columns.items():
                    if i < len(row):
                        record(commodity, unit, row[i])
    elif 'kabupaten bogor' in title.lower():
        # Observed Bogor static layout: commodity × month, explicit annual Jumlah.
        total_indices = {i for r in grid for i,v in enumerate(r) if v.lower() == 'jumlah'}
        unit_match = re.search(r'\((kuintal|kwintal|ton|kg|ribu ton)\)',title,re.I)
        if len(total_indices) != 1 or not unit_match or not any('Januari' in r and 'Desember' in r for r in grid):
            raise BPSError('STATIC PARSER', 'Unsupported annual-total layout; retained for review.')
        total_index = next(iter(total_indices))
        unit = unit_match.group(1).lower()
        unit = 'kw' if unit in ('kwintal','kuintal') else unit
        started = False
        for row in grid:
            if 'Januari' in row and 'Desember' in row:
                started = True
                continue
            if not started or len(row) <= total_index or not row[0] or row[0].startswith('('):
                continue
            if re.match(r'^(jumlah|total|sumber|catatan)',row[0],re.I):
                continue
            # A data row must have all twelve month cells before its explicit total.
            if total_index >= 13 and all(re.fullmatch(r'[\d.,\s–-]+|NA|N/A|', v) for v in row[2:total_index]):
                record(row[0],unit,row[total_index])
    if not rows:
        raise BPSError('STATIC PARSER', 'No unambiguous Kabupaten Bogor annual production rows.')
    return rows, {'rows_rejected':0,'aggregate_rows_excluded':0}
