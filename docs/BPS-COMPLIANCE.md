# Pemeriksaan ketentuan BPS

Tanggal pemeriksaan: 28 September 2026. Cakupan: aplikasi lokal untuk riset/portofolio nonkomersial. Ini pemeriksaan teknis terhadap ketentuan yang tersedia, bukan sertifikasi atau persetujuan BPS.

## Sumber pemeriksaan

- Dokumen bertanda tangan yang diberikan pengguna, `term_of_use_register_rapi_signed.pdf`: empat halaman berisi ketentuan dan satu halaman kosong. Dibaca melalui render Poppler karena struktur PDF menyebabkan kegagalan pembaca teks. Dokumen asli tidak diubah dan tidak dimasukkan ke repositori.
- [Ketentuan WebAPI BPS](https://webapi.bps.go.id/developer/files/term_of_use.pdf), diunduh dari tautan portal resmi dan diperiksa secara visual, empat halaman, bertanggal Desember 2022. Pokok ketentuan yang relevan konsisten dengan dokumen pengguna. Bagian 16 pada dokumen pengguna tampak terpotong; versi publik menjelaskan penggunaan bahasa Indonesia atau Inggris.
- [Ketentuan konten situs BPS](https://www.bps.go.id/id/term-of-use), diakses 28 September 2026. Bagian 12 dokumen API merujuk ketentuan konten; halaman situs yang tersedia sekarang digunakan sebagai pemeriksaan tambahan.

## Temuan dan tindakan

| Ketentuan | Bukti implementasi / hasil |
| --- | --- |
| API bagian 4.B, halaman 2: pemberitahuan wajib pada setiap tayangan | Kalimat persis `Layanan ini menggunakan API Badan Pusat Statistik (BPS).` tampil pada kelima halaman, termasuk loading/error. Juga ada pada deskripsi API dan setiap baris ekspor CSV. |
| API bagian 3.B dan 14.A: token tidak dipinjamkan dan harus dijaga | Token hanya dibaca backend dari `.env`; tidak dikirim frontend. `.env`, cache, dan log lokal diabaikan Git. Respons/cache transport disanitasi, log httpx dimatikan, endpoint resmi HTTPS dibatasi. Jangan membagikan seluruh folder kerja beserta `.env` atau mengaktifkan log URL permintaan. |
| API bagian 4.C dan larangan 4.D: menghormati pembatasan dan stabilitas layanan | Permintaan berurutan dengan jarak minimum satu detik per klien; refresh HTTP dibatasi 15 menit per proses; HTTP 401/403/429 menghentikan seluruh permintaan berikutnya pada sinkronisasi itu. Tidak ada rotasi token/proksi untuk menghindari pembatasan. Cache dan dataset valid sebelumnya dipertahankan. Jeda ini kebijakan aplikasi, bukan kuota yang diumumkan BPS. |
| Konten situs bagian 13.2: kredit, judul, akses, penulis jika ada, tautan langsung | Judul, BPS sebagai sumber/penerbit, tahun, tanggal akses/sinkronisasi dan tautan publik untuk delapan tabel aktif tersedia di provenance, explorer, halaman sumber, dan CSV. URL dicocokkan dengan halaman publik dan ID tabel; tidak menyertakan token. Tabel baru tanpa URL terverifikasi ditandai dan harus dilengkapi sebelum publikasi. |
| Konten situs bagian 13.3-4; API bagian 6 dan 15: layanan/konten dapat berubah atau dihentikan | Halaman sumber menjelaskan bahwa salinan mengikuti tanggal akses dan konten dapat berubah/ditarik. Cache tidak diberi label sebagai data live; kegagalan mempertahankan snapshot yang valid. |
| Konten situs bagian 13.5 dan API bagian 10: tidak menyiratkan dukungan/asosiasi | Seluruh halaman menegaskan aplikasi independen, tidak disponsori/disahkan BPS. Analisis dibedakan dari kesimpulan resmi BPS. Tidak menggunakan logo BPS. |
| API larangan 4.E dan bagian 7: penggunaan untuk pendapatan/perdagangan dibatasi tanpa PKS | Aplikasi tidak mempunyai pembayaran, langganan, penjualan akses API, atau iklan. Lingkup saat ini nonkomersial. Ketentuan umum konten yang memperbolehkan pemanfaatan komersial tidak otomatis membatalkan batas khusus API. Monetisasi memerlukan klarifikasi tertulis/PKS yang sesuai dari BPS. |
| API bagian 2, 3.A dan 11: registrasi akurat, token aplikasi, kewajiban informasi | Belum dapat diverifikasi melalui kode. Pemilik harus memastikan akun/token sah, identitas serta deskripsi/URL aplikasi terdaftar akurat dan diperbarui, dan memenuhi permintaan informasi BPS. Dokumen bertanda tangan saja bukan bukti persetujuan registrasi/PKS. |

## Batas operasional

Jalankan satu backend lokal sesuai `scripts/start-local.ps1`; kontrol jeda ini tidak menjadi pembatas terdistribusi jika beberapa proses/komputer menggunakan token yang sama. Jangan menjalankan diagnosa jaringan berulang atau restart untuk menghindari pembatasan. Setelah penolakan BPS, periksa akun, kuota, dan instruksi BPS sebelum mencoba lagi. Saat publikasi, refresh wajib dilindungi autentikasi operator dan pembatasan bersama; pemeriksaan Origin saja bukan autentikasi publik. Konfigurasi saat ini hanya mendengarkan loopback.

Dataset statistik tidak diubah dalam pemeriksaan ini. URL publik hanya metadata kutipan. Nilai yang hilang tetap kosong dan hasil analisis tetap milik aplikasi dalam arti tanggung jawab analisis, tanpa klaim kepemilikan atas konten BPS.

## Kesimpulan terbatas

Kekurangan pemberitahuan wajib dan tautan sumber pada aplikasi lokal sudah diperbaiki, dan perlindungan beban API diperkuat. Kepatuhan penuh tetap bergantung pada validitas serta kecocokan registrasi/token, tujuan penggunaan yang sebenarnya, perjanjian tambahan, perubahan ketentuan BPS, dan cara penerapan ketika dipublikasikan. Tidak ada kontak atau pengajuan ke BPS yang dilakukan oleh pemeriksaan ini.
