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


### GitHub deployment preparation, 28 September 2026

- 31 backend tests pass, including public refresh denial without Origin and local cooldown. Also checked with BPS_API_KEY empty as on CI.
- GitHub Pages static export passes with /bogor-agricultural-intelligence basePath and a dummy HTTPS backend origin used only for compilation.
- All five exported routes have repository-prefixed links/assets and the required BPS notice.
- Static export scanned against the locally configured BPS token: no matches.
- Docker engine is not installed here; container build/runtime and actual GitHub/hosting deployment are not yet verified. No live deployment or repository push performed.

### Bundled snapshot wiring, 28 September 2026

- 32 backend tests pass, including the new read-only snapshot fallback and writable-cache precedence.
- Production simulation (empty `BPS_CACHE_DIR`, `BPS_API_KEY` blank, `PUBLIC_DEPLOYMENT=true`) served the bundled snapshot with no BPS credentials: 8 selected tables of 18 discovered, 40 kecamatan, default 2025/`kw` total 2,439,670.97, 2,120 rows, 2,121-line CSV carrying the API notice, 6 insights, 5 trend points, and a source URL on all 8 tables.
- `POST /api/bps/refresh` returned 403 both with and without an Origin header.
- Pages export rebuilt with a dummy HTTPS origin: all five routes present, assets repo-prefixed, mandatory BPS notice on every page, no `Refresh data` control in the emitted HTML.
- The export still contains the literal `BPS_API_KEY` inside an operator-facing UI message that is guarded off whenever a remote backend origin is configured. No value assignment and no token appears in any chunk.
- Docker image build, Render runtime and the live GitHub Pages deployment remain unverified; no Docker engine is installed here.
