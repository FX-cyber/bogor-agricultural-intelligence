# GitHub Pages saja

Situs ini sepenuhnya statis: tidak memerlukan Render, kartu, backend online, atau API key di GitHub. Tidak ada permintaan ke BPS saat pengunjung membuka situs.

## Publikasi

1. Push proyek ke cabang `main` di GitHub.
2. Repository → Settings → Pages → Source: **GitHub Actions**.
3. Workflow **Deploy GitHub Pages** otomatis mengekspor snapshot, memeriksa hasil perhitungan, membangun frontend, dan menerbitkan situs.
4. URL proyek ini: https://fx-cyber.github.io/bogor-agricultural-intelligence/

Tidak ada repository variable atau secret yang diperlukan. `NEXT_PUBLIC_API_BASE_URL` tidak digunakan workflow. `basePath` otomatis mengikuti konfigurasi Pages.

## Data dan perhitungan

Input build adalah `backend/data/snapshot/normalized.json.gz`, snapshot publik yang sudah dibersihkan dari token dan metadata internal. `backend/scripts/export_pages.py` menghasilkan payload browser ringkas dan hasil K-Means per kombinasi tahun/satuan/kategori. File publik dihasilkan saat build, bukan mengambil data baru dari BPS.

Semua filter, pencarian literal, urutan, pagination, CSV, total, YoY berpasangan, peringkat, tren panel lengkap, volatilitas, dan insight memakai observasi snapshot yang sama. K-Means memakai implementasi Python/scikit-learn asli saat build. Filter satu kecamatan atau satu komoditas tidak memenuhi syarat minimum cluster; aplikasi menampilkan ketidaktersediaan dengan jelas.

Tampilan memuat timestamp snapshot dan sumber tabel. Data tidak otomatis menjadi terbaru; untuk memperbarui, jalankan pipeline lokal sesuai README, ekspor ulang snapshot publik yang disanitasi, periksa datanya, lalu commit snapshot baru. Jangan commit `.env`, cache mentah, atau token BPS.

Browser modern yang mendukung `DecompressionStream` diperlukan untuk memuat snapshot gzip. Data diunduh sekali per halaman dan semua interaksi berikutnya berlangsung lokal.

## Uji lokal mode publik (PowerShell)

```powershell
backend\.venv\Scripts\python backend\scripts\export_pages.py
node --experimental-strip-types frontend/tests/static-analytics.mjs
cd frontend
$env:DEPLOY_TARGET = 'github-pages'
$env:PAGES_BASE_PATH = '/bogor-agricultural-intelligence'
npm ci
npm run build
```

Hasil statis ada di `frontend/.next-pages`. Sajikan folder itu di subpath yang sama saat melakukan preview. Backend lokal lama tetap tersedia untuk pengembangan; mode tersebut tidak dipakai deployment Pages.

## Ketentuan penggunaan

Pemberitahuan API, kredit BPS, tanggal akses, tautan sumber, dan penegasan aplikasi independen tetap tampil. Tidak ada token atau kredensial di file publik. Lingkup tetap riset/portofolio nonkomersial; lihat BPS-COMPLIANCE.md. File Docker hanya opsi pengembangan lama, bukan persyaratan publikasi.
