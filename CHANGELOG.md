# Catatan Perubahan

Seluruh perubahan penting pada proyek ini dicatat di sini, beserta alasannya.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/), penomoran mengikuti [Semantic Versioning](https://semver.org/lang/id/).

---

## [0.2.0] — 2026-09-24

### Ditambahkan

- **Sakelar arsip bukti.** Parameter `enableStorage` pada Bicep, dikendalikan lewat variabel `ENABLE_STORAGE`, mati secara bawaan.
  ```powershell
  azd env set ENABLE_STORAGE true
  azd up
  ```
  Saat dinyalakan, penerapan membuat storage account, kontainer `bukti`, peran `Storage Blob Data Contributor`, serta mengisi `AZURE_STORAGE_ACCOUNT_URL` dan `AZURE_STORAGE_CONTAINER` pada aplikasi.

### Diubah

- Variabel lingkungan Container App disusun dengan `concat()` agar bagian storage dapat ditambahkan secara bersyarat.
- Output `storageAccountUrl` memakai akses aman `?.` dengan nilai jatuh `''`.

### Catatan

Kode aplikasi **tidak berubah sama sekali**. `storage.py` memang sudah membaca `settings.storage_enabled`, sehingga cukup infrastrukturnya yang disesuaikan.

Perubahan ini menjawab kebutuhan mencoba di langganan lain yang tidak menerapkan policy pembatasan akses jaringan pada storage.

---

## [0.1.0] — 2026-09-24

Rilis pertama. Demo berjalan di Azure dan sudah diuji dari ujung ke ujung.

### Ditambahkan

**Aplikasi**

- API FastAPI dengan tiga rute: halaman demo, `GET /api/health`, dan `POST /api/review`.
- Halaman demo untuk mengunggah foto, mengisi koordinat dan alamat pengajuan, lalu menampilkan hasil beserta foto sumbernya.
- Ekstraksi temuan dari foto memakai model multimodal `gpt-5-mini` di Azure AI Foundry.
- Analisis lokasi memakai Azure Maps: reverse geocode, geocode alamat pengajuan, dan rute kendaraan.
- Deteksi foto yang dipakai ulang memakai sidik gambar dan jarak Hamming.
- Pemeriksaan kelengkapan foto wajib.
- Rekomendasi tindak lanjut berbasis aturan: `lengkap`, `perlu_bukti_tambahan`, atau `perlu_kunjungan`.

**Infrastruktur**

- Penerapan satu perintah dengan `azd up`, memakai Bicep.
- Seluruh sumber daya berada dalam satu resource group.
- Seluruh akses antarlayanan memakai user-assigned Managed Identity, tanpa kunci maupun connection string.
- Autentikasi lokal dimatikan pada AI Services dan Azure Maps.
- Image dibangun di ACR, sehingga Docker lokal tidak diperlukan.

**Dokumentasi**

- `README.md` sebagai pintu masuk.
- `docs/PRD.md` berisi tujuan produk, lingkup, dan batasannya.
- `docs/TRACE.md` menelusuri alur dari browser sampai kembali ke browser.
- `docs/CODE.md` berisi referensi teknis untuk pengembang.
- `docs/DEPLOYMENT.md` berisi cara menerapkan, memperbarui, dan menghapus.

### Keputusan Rancangan

| Keputusan | Alasan |
|---|---|
| Rekomendasi dihasilkan aturan, bukan model | Harus dapat dibaca dan diaudit manusia |
| `creditDecision` dan `propertyValue` selalu kosong | Batas produk yang disengaja, ditegakkan di kode |
| Setiap bidang temuan menyediakan `tidak_dapat_dinilai` | Mencegah model menebak |
| Setiap temuan menyebut foto sumbernya | Agar hasil dapat ditelusuri petugas |
| Susunan jalan tidak disimpulkan dari foto | Hanya peta dan protokol perekaman yang dapat menjawabnya |
| Kegagalan peta dan penyimpanan tidak menggugurkan permintaan | Hasil sebagian tetap berguna |
| Identitas bertipe user-assigned | Peran dapat diberikan sebelum sumber daya lain berdiri, dan tetap sama saat diterapkan ulang |
| Replika dibatasi satu | Indeks sidik berada di memori saat arsip mati |

### Kendala yang Ditemukan Saat Penerapan

| Kendala | Penyelesaian |
|---|---|
| Model keluarga GPT-5 menolak `temperature` selain nilai bawaan | Parameter dihapus dari pemanggilan. Akibatnya hasil dapat bervariasi antarpercobaan |
| Tag base image `devcontainers/python:3.12-bookworm-slim` tidak ada | Berpindah ke `azurelinux/base/python`, lebih ringan dan tanpa batas tarik Docker Hub |
| pip bawaan Azure Linux dipasang lewat rpm sehingga tidak dapat ditimpa | Langkah upgrade pip dihapus dari `Dockerfile` |
| Azure Policy memaksa `publicNetworkAccess` storage menjadi `Disabled`, bahkan saat Bicep menyetelnya `Enabled` | Blob Storage dimatikan pada demo. Dikembalikan sebagai sakelar pada 0.2.0 |
| Nama storage account melebihi batas 24 karakter | Dipotong dengan `take()` |
| `azd provision` mengembalikan image Container App ke placeholder | Selalu memakai `azd up`, dicatat di dokumentasi |
| Peran data plane memerlukan waktu menyebar | Ditunggu, dan dicatat sebagai gejala yang dikenali |

### Perapian Kode

| Perubahan | Berkas |
|---|---|
| Menghapus atribut `main_road_classes` yang tidak dipakai | `config.py` |
| Memindahkan ambang duplikasi ke konfigurasi | `config.py`, `main.py` |
| Menghapus parameter `filename` yang tidak dipakai | `vision.py` |
| Balasan model tidak sah melempar `ValueError` beserta cuplikannya | `vision.py` |
| Mempersempit penangkapan galat ke `ResourceExistsError` | `storage.py` |
| Memberi nama konstanta `ROUTE_PROBE_OFFSET_DEG` | `maps.py` |
| Mengganti rantai `and` dengan daftar agar tidak ada hubungan pendek yang menyesatkan | `main.py` |

### Batasan yang Diketahui

- Endpoint `POST /api/review` belum terlindungi autentikasi.
- Belum ada pembatasan laju maupun batas ukuran unggahan.
- Belum ada pengujian otomatis.
- Sidik gambar memakai aHash, lemah terhadap pemotongan dan perputaran.
- Pencocokan foto wajib memakai potongan nama berkas.

Rinciannya ada di `docs/CODE.md` bagian 9.
