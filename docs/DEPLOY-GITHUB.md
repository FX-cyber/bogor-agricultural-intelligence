# Deploy dari GitHub

Proyek mendukung GitHub Pages untuk frontend dan backend Python/Docker terpisah. GitHub Pages tidak menjalankan Python/FastAPI. Semua filter, analisis statistik, clustering, dan ekspor tetap menggunakan backend; tanpa backend, situs menampilkan kesalahan ketersediaan data, bukan data contoh.

## 1. Upload kode

Buat repositori GitHub lalu unggah isi proyek atau isi ZIP distribusi, dengan `.github`, `frontend`, `backend`, dan `render.yaml` berada di akar repositori. Gunakan cabang `main`. Jangan unggah folder proyek mentah lewat ZIP buatan sendiri yang menyertakan `.env`, `.local`, cache, atau virtualenv.

Alternatif terminal, dari folder proyek ini (ganti URL dengan repositori Anda):

```powershell
git init -b main
git add .
git status
git commit -m "Prepare BPS analytics for GitHub Pages"
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

`.gitignore` mengecualikan rahasia, cache, dependensi, dan keluaran build. Periksa daftar file staged sebelum commit. Tidak ada token yang perlu disimpan sebagai GitHub Actions secret untuk workflow Pages ini.

## 2. Deploy backend

Opsi siap pakai: buat Blueprint di Render dari repositori ini; `render.yaml` menggunakan `backend/Dockerfile`. Tinjau paket/biaya pada penyedia sebelum membuat layanan. Dockerfile juga dapat dijalankan pada hosting Docker lain.

Isi environment di hosting backend:

| Nama | Nilai |
| --- | --- |
| `PUBLIC_DEPLOYMENT` | `true` (sudah menjadi default Dockerfile dan Blueprint) |
| `ALLOWED_ORIGINS` | `https://USERNAME.github.io` tanpa path repositori; gunakan origin domain sendiri jika memakai custom domain |
| `BPS_CACHE_DIR` | Opsional: direktori cache yang writable; default `/app/data/cache` di Docker |

**Jangan menyetel `BPS_API_KEY` di hosting publik.** Image Docker menyertakan snapshot baca-saja `backend/data/snapshot/normalized.json.gz`, dan backend memakainya ketika cache kosong. Tanpa token, startup tidak melakukan panggilan BPS sama sekali, sehingga paket gratis ber-disk ephemeral tetap aman: restart maupun spin-down tidak memicu unduh ulang data. Token BPS hanya berada di mesin operator.

`PORT` disediakan hosting atau default 8000. Jalankan satu worker dan satu instance. Request publik tidak dapat memicu refresh, termasuk tanpa header Origin. `/api/health` hanya menunjukkan server hidup, sedangkan `/api/bps/status` menunjukkan status data. Pastikan `tables_selected` lebih dari nol dan tidak ada error sebelum memakai situs.

Snapshot diperbarui dari mesin operator, bukan dari server publik. Penyimpanan persisten tidak diperlukan selama backend berjalan tanpa token; bila Anda memang menyetel token, siapkan disk persisten yang dapat ditulis UID `appuser` agar restart tidak mengunduh ulang seluruh data, dan jangan menambah replica dengan token yang sama.

Simpan URL HTTPS backend, misalnya `https://NAMA-API.onrender.com` (contoh saja). Backend harus memiliki TLS yang valid. CORS memakai origin frontend saja, bukan `/REPOSITORY`.

## 3. Aktifkan GitHub Pages

1. Repository → **Settings → Secrets and variables → Actions → Variables**.
2. Tambahkan repository variable **`NEXT_PUBLIC_API_BASE_URL`** dengan URL HTTPS backend, tanpa slash di akhir. Ini URL publik, bukan token BPS.
3. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Buka **Actions → Deploy GitHub Pages → Run workflow**, atau push perubahan ke `main`.
5. Buka URL dari hasil job `deploy`. Workflow menyesuaikan `basePath` dengan konfigurasi Pages, sehingga repositori project, situs `USERNAME.github.io`, dan custom domain mengikuti base path yang dilaporkan GitHub.

Jika run awal gagal karena variable atau Pages belum disetel, selesaikan langkah di atas dan jalankan ulang. Jika mengganti URL backend, jalankan build/deploy ulang karena environment frontend ditanam saat build.

## Pengujian lokal mode Pages

```powershell
cd frontend
$env:DEPLOY_TARGET = 'github-pages'
$env:NEXT_PUBLIC_API_BASE_URL = 'https://URL-BACKEND-ANDA'
$env:PAGES_BASE_PATH = '/NAMA-REPOSITORI'
npm ci
npm run build
```

Keluaran statis ada di `frontend/.next-pages` sesuai `distDir` pada mode export, agar build lokal `.next` tidak terganggu. Untuk kembali ke mode lokal, hapus ketiga environment di atas dari shell, lalu jalankan frontend/backend sesuai README. `next start` digunakan untuk build lokal, bukan folder `.next-pages`.

## Pembaruan data dan ketentuan BPS

Situs publik menampilkan snapshot dengan waktu akses; tidak mengaku live. Tombol refresh hanya tersedia pada mode lokal. Untuk memperbarui data publik, operator menyegarkan data di mesin sendiri lalu mengganti snapshot yang dibundel:

```powershell
# setelah refresh lokal sukses menghasilkan backend/data/cache/normalized.json
gzip -9 -c backend/data/cache/normalized.json > backend/data/snapshot/normalized.json.gz
git add backend/data/snapshot/normalized.json.gz
git commit -m "Update BPS data snapshot"
git push
```

Deploy ulang backend saja; frontend tidak perlu dibangun ulang karena URL backend tidak berubah. Jangan restart berulang untuk menghindari pembatasan BPS. Rilis ini tidak memasang scheduler otomatis.

Pendaftaran/URL aplikasi BPS harus sesuai deployment. Jangan membuat token BPS sebagai variable `NEXT_PUBLIC_*`, memasukkannya ke GitHub, atau membagikannya ke pengunjung. Cek [pemeriksaan ketentuan](BPS-COMPLIANCE.md); lingkup yang disiapkan tetap nonkomersial.

Rujukan: [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), [Next.js deployment](https://nextjs.org/docs/pages/getting-started/deploying), [Render persistent disks](https://render.com/docs/disks).
