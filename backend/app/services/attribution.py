"""Public table links verified against BPS pages on 2026-09-28.
These are citation metadata, never observations. Unknown tables have no guessed URL.
"""
NOTICE = 'Layanan ini menggunakan API Badan Pusat Statistik (BPS).'
TABLE_URLS = {
    "SGJsZ0s5RjRyTWN1eDNyUERzbTI0Zz09": "https://bogorkab.bps.go.id/id/statistics-table/3/U0dKc1owczVSalJ5VFdOMWVETnlVRVJ6YlRJMFp6MDkjMw%3D%3D/pro",
    "eHEwRmg2VUZjY2lWNWNYaVhQK1h4QT09": "https://bogorkab.bps.go.id/id/statistics-table/3/ZUhFd1JtZzJWVVpqWTJsV05XTllhVmhRSzFoNFFUMDkjMw%3D%3D/produksi-tanaman-sayuran-menurut-kecamatan-dan-jenis-tanaman-di-kabupaten-bogor--2018.html",
    "bXNVb1pmZndqUDhKWElUSjhZRitidz09": "https://bogorkab.bps.go.id/id/statistics-table/3/YlhOVmIxcG1abmRxVURoS1dFbFVTamhaUml0aWR6MDkjMw%3D%3D/luas-panen-tanaman-sayuran-menurut-kecamatan-dan-jenis-tanaman-di-kabupaten-bogor--2021.html",
    "UVMzY2pGV3kyWjhLYm9UTEdtYk52Zz09": "https://bogorkab.bps.go.id/id/statistics-table/3/VVZNelkycEdWM2t5V2poTFltOVVURWR0WWs1Mlp6MDkjMw%3D%3D/produksi-tanaman-biofarmaka-menurut-kecamatan-dan-jenis-tanaman-di-kabupaten-bogor--2019.html",
    "MDNRYkxNYzdGaG1XY2hrM256MlRLQT09": "https://bogorkab.bps.go.id/id/statistics-table/3/TUROUllreE5ZemRHYUcxWFkyaHJNMjU2TWxSTFFUMDkjMw%3D%3D/produksi-tanaman-hias-menurut-kecamatan-dan-jenis-tanaman---di-kabupaten-bogor--2023.html",
    "MnBlci91MjhhS1Fxb1ZmS2NCVUxVZz09": "https://bogorkab.bps.go.id/id/statistics-table/3/TW5CbGNpOTFNamhoUzFGeGIxWm1TMk5DVlV4Vlp6MDkjMw%3D%3D/luas-panen-tanaman-biofarmaka-menurut-kecamatan-dan-jenis-tanaman-di-kabupaten-bogor--2019.html",
    "bWJLbGZJZXBoaTQ1VC9LQkZRa1NzQT09": "https://bogorkab.bps.go.id/id/statistics-table/3/YldKTGJHWkpaWEJvYVRRMVZDOUxRa1pSYTFOelFUMDkjMw%3D%3D/luas-panen-tanaman-hias-menurut-kecamatan-dan-jenis-tanaman-di-kabupaten-bogor--2022.html",
    "elJzMTFDZWI0bS9OcGptMVFWNEdhdz09": "https://bogorkab.bps.go.id/id/statistics-table/3/ZWxKek1URkRaV0kwYlM5T2NHcHRNVkZXTkVkaGR6MDkjMw%3D%3D/produksi-perkebunan-menurut-kecamatan-dan-jenis-tanaman-di-kabupaten-bogor--ribu-ton---2023.html"
}

def source_url(table_id, year=None):
    url = TABLE_URLS.get(str(table_id))
    return f'{url}?year={int(year)}' if url and year is not None else url

