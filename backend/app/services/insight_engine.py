from app.services.analytics import summarize, production, trends, matched_change, provenance


def insights(rows, filters, cluster_result=None):
    summary = summarize(rows, filters)
    frame, unit, _ = production(rows, filters)
    year, total = summary['year'], summary['total']
    if total is None:
        return []
    current = frame[frame.year == year]
    result = []

    def add(kind, severity, title, message, evidence, priority, sources=None):
        result.append({'type': kind, 'severity': severity, 'title': title, 'message': message,
                       'evidence': evidence, 'priority': priority, 'provenance': sources or summary['provenance']})

    if summary['top_commodities'] and total > 0:
        leader = summary['top_commodities'][0]
        share = leader['value'] / total * 100
        add('leader', 'positive', 'Komoditas dengan produksi terbesar',
            f"{leader['name']} menyumbang {share:.1f}% dari produksi tercatat pada {year} ({unit}).",
            {'commodity': leader['name'], 'production': leader['value'], 'total': total, 'share_percent': share}, 75)
        if share >= 40:
            add('concentration', 'neutral', 'Produksi terkonsentrasi',
                f"{share:.1f}% volume tercatat berasal dari satu komoditas. Ini ukuran konsentrasi volume, bukan nilai ekonomi.",
                {'commodity': leader['name'], 'share_percent': share}, 78)
    if summary['top_districts']:
        top = summary['top_districts'][0]
        add('leader', 'positive', 'Sentra produksi tercatat',
            f"{top['name']} memiliki produksi tercatat tertinggi pada pilihan {year}: {top['value']:,.2f} {unit}.",
            top, 70)
    changes = []
    for name, group in frame.groupby('commodity'):
        change, _ = matched_change(group, year)
        if change['change_percent'] is not None:
            changes.append((name, change, group))
    # Relative materiality threshold avoids tiny denominators; transparent evidence.
    previous_total = sum(c['previous'] for _, c, _ in changes)
    threshold = previous_total * .01
    eligible = [(n, c, g) for n, c, g in changes if c['previous'] >= threshold and c['previous'] > 0
                and c['matched_observations'] >= .8 * max(c['current_observations'], c['previous_observations'])]
    for kind, sign, title in [('growth', 1, 'Pertumbuhan persentase tertinggi'), ('decline', -1, 'Penurunan produksi terbesar')]:
        choices = [x for x in eligible if sign * x[1]['change_percent'] >= 5]
        if choices:
            name, change, group = max(choices, key=lambda x: sign * x[1]['change_percent'])
            add(kind, 'positive' if sign == 1 else 'warning', title,
                f"{name} {'meningkat' if sign == 1 else 'turun'} {abs(change['change_percent']):.1f}% pada {year} dibanding {year-1}, pada kecamatan dengan data di kedua tahun.",
                {**change, 'minimum_base': threshold, 'unit': unit}, 85 + min(10, abs(change['change_percent']) / 10), provenance(group))
    history = trends(rows, filters)['commodity_trends']
    if history:
        trend = max(history, key=lambda x: abs(x['relative_slope']))
        add('trend', 'neutral', 'Arah perubahan antar tahun',
            f"{trend['commodity']}: {trend['classification']}, berdasarkan {trend['observations']} observasi tahunan pada {trend['districts']} kecamatan dengan data lengkap.",
            {k: v for k, v in trend.items() if k != 'provenance'}, 60, trend['provenance'])
        volatile = max(history, key=lambda x: x['cv'])
        if volatile['cv'] >= .3:
            add('volatility', 'warning', 'Variasi produksi tinggi',
                f"{volatile['commodity']} menunjukkan variasi relatif tertinggi pada panel yang lengkap (CV {volatile['cv']:.2f}).",
                {k: v for k, v in volatile.items() if k != 'provenance'}, 80, volatile['provenance'])
    if summary['missing']:
        add('data_quality', 'warning', 'Cakupan data perlu diperhatikan',
            f"{summary['missing']} dari {summary['observations']} observasi tidak memiliki nilai. Total dan peringkat hanya mencakup nilai tersedia.",
            {'missing': summary['missing'], 'observations': summary['observations']}, 100)
    if cluster_result and cluster_result.get('available'):
        add('cluster', 'neutral', 'Pola produksi kecamatan',
            f"K-Means menemukan {cluster_result['k']} kelompok pada {len(cluster_result['points'])} kecamatan yang memenuhi cakupan minimum.",
            {'silhouette': cluster_result['silhouette'], 'k': cluster_result['k'], 'features': cluster_result['features']}, 65)
    return sorted(result, key=lambda i: -i['priority'])[:6]
