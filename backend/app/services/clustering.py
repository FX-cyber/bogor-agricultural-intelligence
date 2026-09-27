import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from app.services.analytics import production, records, matched_change


def features(rows, filters):
    frame, unit, _ = production(rows, filters)
    frame = frame[frame.geography_level == 'kecamatan']
    year = int(filters.get('year') or frame.year.max()) if not frame.empty else None
    current = frame[frame.year == year]
    result = []
    for name, group in current.groupby('district'):
        valid = group.dropna(subset=['value'])
        # Sparse district totals are not reliable production features.
        if len(valid) < 2 or len(valid) / len(group) < .6:
            continue
        history = frame[frame.district == name]
        change, _ = matched_change(history, year)
        panel = history.pivot_table(index='commodity', columns='year', values='value', aggfunc='first').dropna()
        annual = panel.sum(axis=0)
        cv = float(annual.std(ddof=1) / annual.mean()) if panel.shape[1] >= 3 and len(panel) and annual.mean() > 0 else np.nan
        result.append({'district': name, 'total_production': float(valid.value.sum()),
                       'average_production': float(valid.value.mean()),
                       'active_commodities': int((valid.value > 0).sum()),
                       'yoy_growth': change['change_percent'], 'production_volatility': cv,
                       'coverage': len(valid) / len(group)})
    return pd.DataFrame(result), unit, year


def cluster(rows, filters):
    frame, unit, year = features(rows, filters)
    unavailable = {'available': False, 'message': 'Data belum mencukupi untuk analisis cluster yang reliabel.',
                   'eligible_districts': len(frame), 'unit': unit, 'year': year}
    if len(frame) < 6:
        return unavailable
    names = ['total_production', 'average_production', 'active_commodities', 'yoy_growth', 'production_volatility']
    names = [n for n in names if frame[n].notna().mean() >= .6 and frame[n].nunique() > 1]
    if len(names) < 2:
        return unavailable
    matrix = StandardScaler().fit_transform(SimpleImputer(strategy='median').fit_transform(frame[names]))
    unique = len(np.unique(matrix, axis=0))
    candidates = []
    with threadpool_limits(limits=1):
        for k in range(2, min(6, len(frame) - 1, unique) + 1):
            model = KMeans(n_clusters=k, n_init=20, random_state=42).fit(matrix)
            if min(np.bincount(model.labels_)) < 2:
                continue
            candidates.append((float(silhouette_score(matrix, model.labels_)), k, model.labels_))
    if not candidates or max(c[0] for c in candidates) <= 0:
        return unavailable
    score, k, labels = max(candidates, key=lambda x: (x[0], -x[1]))
    frame['cluster'] = labels
    centroids = []
    overall = frame.total_production.median()
    diversity = frame.active_commodities.median()
    for label, group in frame.groupby('cluster'):
        values = {n: float(group[n].mean()) if group[n].notna().any() else None for n in names}
        description = ('Produksi di atas median' if group.total_production.mean() > overall else 'Produksi di bawah/setara median')
        description += '; diversifikasi ' + ('di atas median' if group.active_commodities.mean() > diversity else 'di bawah/setara median')
        centroids.append({'id': int(label), 'name': f'Cluster {chr(65 + label)}',
                          'description': description, 'districts': group.district.tolist(), 'centroid': values})
    return {'available': True, 'k': k, 'silhouette': score, 'features': names, 'unit': unit, 'year': year,
            'points': records(frame), 'clusters': centroids,
            'candidates': [{'k': n, 'silhouette': s} for s, n, _ in candidates],
            'method': '≥60% observed commodity cells; ≥6 districts; median imputation; StandardScaler; k=2..6; minimum 2 members/cluster. Exploratory, not causal.'}
