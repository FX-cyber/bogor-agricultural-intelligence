import json
import numpy as np
import pandas as pd
from app.services.normalizer import FIELDS
from app.services.attribution import source_url


def records(frame):
    return json.loads(frame.to_json(orient='records', force_ascii=False))


def yoy(current, previous):
    if current is None or previous is None or pd.isna(current) or pd.isna(previous) or previous <= 0:
        return None
    return float((current - previous) / previous * 100)


def filtered(rows, filters, include_year=True):
    frame = pd.DataFrame(rows, columns=FIELDS)
    frame['source_url'] = [source_url(r['source_table_id'], r['year']) for r in rows]
    for key in ('year', 'district', 'commodity', 'category', 'unit', 'indicator'):
        value = filters.get(key)
        if value not in (None, '') and (key != 'year' or include_year):
            frame = frame[frame[key] == (int(value) if key == 'year' else value)]
    return frame


def production(rows, filters):
    frame = filtered(rows, {**filters, 'indicator': 'Produksi'}, include_year=False)
    # Never blend administrative levels or unknown/incompatible units.
    if 'kecamatan' in frame.geography_level.values:
        frame = frame[frame.geography_level == 'kecamatan']
    units = sorted(frame.unit.dropna().unique().tolist())
    selected = filters.get('unit') or (units[0] if len(units) == 1 else None)
    if not selected:
        return frame.iloc[:0], None, units
    return frame[frame.unit == selected], selected, units


def matched_change(frame, year):
    keys = ['district_code', 'commodity', 'category', 'unit']
    current = frame[(frame.year == year) & frame.value.notna()]
    previous = frame[(frame.year == year - 1) & frame.value.notna()]
    pairs = current.merge(previous, on=keys, suffixes=('_current', '_previous'))
    a, b = (float(pairs.value_current.sum()), float(pairs.value_previous.sum())) if len(pairs) else (None, None)
    return {'current': a, 'previous': b, 'change_percent': yoy(a, b), 'matched_observations': len(pairs),
            'current_observations': len(current), 'previous_observations': len(previous),
            'basis': 'Matched district × commodity observations; previous calendar year'}, pairs


def ranking(frame, key):
    result = frame.dropna(subset=['value']).groupby(key).value.sum(min_count=1).sort_values(ascending=False)
    return [{'name': name, 'value': float(value)} for name, value in result.items()]


def provenance(frame):
    cols = ['source', 'source_table_id', 'source_table_title', 'year', 'last_synced', 'last_updated', 'source_url']
    return records(frame[cols].drop_duplicates())


def summarize(rows, filters):
    frame, unit, units = production(rows, filters)
    year = int(filters.get('year') or frame.year.max()) if not frame.empty else filters.get('year')
    current = frame[frame.year == year]
    valid = current.dropna(subset=['value'])
    change, _ = matched_change(frame, year) if year else ({'change_percent': None}, None)
    return {'year': year, 'unit': unit, 'available_units': units,
            'total': float(valid.value.sum()) if len(valid) else None,
            'yoy': change, 'active_commodities': int(valid[valid.value > 0].commodity.nunique()),
            'district_count': int(valid[valid.geography_level == 'kecamatan'].district.nunique()), 'observations': len(current),
            'missing': int(current.value.isna().sum()), 'top_commodities': ranking(current, 'commodity'),
            'top_districts': ranking(current[current.geography_level == 'kecamatan'], 'district'), 'provenance': provenance(current),
            'message': 'Pilih satu satuan untuk analisis.' if len(units) > 1 and not unit else None}


def trends(rows, filters):
    frame, unit, _ = production(rows, filters)
    annual = frame.groupby('year').value.sum(min_count=1)
    series = [{'year': int(y), 'value': None if pd.isna(v) else float(v)} for y, v in annual.items()]
    results = []
    for name, group in frame.groupby('commodity'):
        # Stable district panel across all years: missingness must not masquerade as a trend.
        pivot = group.pivot_table(index='district_code', columns='year', values='value', aggfunc='first')
        pivot = pivot.dropna()
        if pivot.shape[1] < 3 or pivot.empty:
            continue
        values = pivot.sum(axis=0)
        mean = float(values.mean())
        if mean <= 0:
            continue
        slope = float(np.polyfit(values.index.astype(float), values.values, 1)[0])
        results.append({'commodity': name, 'slope': slope, 'relative_slope': slope / mean,
                        'classification': 'Increasing' if slope / mean > .02 else 'Decreasing' if slope / mean < -.02 else 'Stable',
                        'observations': len(values), 'districts': len(pivot), 'cv': float(values.std(ddof=1) / mean),
                        'unit': unit, 'provenance': provenance(group)})
    return {'series': series, 'unit': unit, 'commodity_trends': results,
            'note': 'Annual totals include available observations. Trend/CV use a complete district panel (≥3 years).'}
