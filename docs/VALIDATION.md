# Validation record — 27 September 2026

- Authenticated BPS domain discovery verified Jawa Barat 3200 and Bogor 3201.
- SIMDASI confirmed Kabupaten Bogor, wilayah code 3201000, 18 agricultural candidates.
- Eight production/harvest tables ingested for explicit available years, 2021–2025.
- 30,120 normalized rows, 8,513 numeric values, 21,607 missing values, 40 districts.
- 37 aggregate geography rows excluded; no duplicate conflicts or unknown units.
- Live static detail fallback `/v1/api/view` succeeded after `/v1/view` returned 404.
- Static province fixture confirms Kabupaten Bogor is isolated from Kota Bogor.
- 27 offline backend tests passed across the full run and final cache-regression run; Python compilation passed.
- Next.js production build and TypeScript checks passed for all five application routes.
- Browser verified default dashboard, category filter changes, searchable data explorer,
  source metadata and desktop/mobile layouts. Screenshots are in `screenshots/`.
- Keyboard activation of the dashboard refresh control successfully started a live
  BPS refresh; completion reported `api_connected=true`, `refreshing=false`, no error.
- Additional regression proves a partial refresh cannot replace a complete valid cache.
- Source/fixture/documentation credential scan found zero matches outside `.env`.

The default all-category kw dataset does not meet clustering coverage requirements;
the UI correctly displays insufficient-data state. Synthetic clustering tests verify
feature engineering and silhouette selection without serving synthetic data.

Limits: no fabricated boundary map; unsupported BPS HTML/dynamic schemas are rejected.
The app is configured for a single local process, not a publicly authenticated service.

### Pemeriksaan ketentuan, 28 September 2026

30 tes backend lulus, termasuk penghentian HTTP 401/403/429, cooldown refresh, dan provenance/CSV dengan tautan sumber serta pemberitahuan API. TypeScript tanpa error. Statistik sumber tidak diubah. Lihat BPS-COMPLIANCE.md untuk cakupan dan hal yang belum dapat diverifikasi.

