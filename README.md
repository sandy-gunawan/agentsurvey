# Asisten Review Bukti Survei Rumah

Demo untuk perusahaan pembiayaan. Foto survei rumah dan titik koordinat diubah menjadi **data terstruktur**, dibandingkan dengan **data pengajuan**, lalu disajikan sebagai **draf temuan dan rekomendasi tindak lanjut**.

> Sistem ini **tidak** menentukan nilai properti dan **tidak** mengambil keputusan kredit. Ruas `creditDecision` dan `propertyValue` selalu kosong, dan hal itu ditegakkan di kode.

---

## Apa yang Dikerjakan

| Sumber | Yang dihasilkan |
|---|---|
| Foto | Jumlah lantai, jenis bangunan, material dinding dan atap, tempat parkir, permukaan jalan, nomor rumah |
| Koordinat | Alamat hasil peta, kecocokan dengan alamat pengajuan, keterjangkauan mobil, jarak ke jalan kendaraan |
| Keduanya | Kelengkapan bukti, foto yang dipakai ulang, rekomendasi tindak lanjut |

Rekomendasi dihasilkan **aturan yang dapat dibaca manusia**, bukan oleh model. Model hanya mengisi temuan.

---

## Menjalankan

```powershell
azd auth login
az login
azd up
```

Menghapus seluruhnya:

```powershell
azd down --force --purge
```

Rinciannya ada di [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Arsitektur

Seluruh sumber daya berada dalam satu resource group, dan **seluruh akses antarlayanan memakai Managed Identity tanpa satu pun kunci**.

| Layanan | Fungsi |
|---|---|
| Azure Container Apps | Aplikasi web dan API |
| Azure AI Services + `gpt-5-mini` | Ekstraksi data dari foto |
| Azure Maps | Reverse geocode, geocode, rute kendaraan |
| Azure Container Registry | Image aplikasi |
| Log Analytics + Application Insights | Pemantauan |

---

## Dokumentasi

| Dokumen | Untuk siapa |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Memahami tujuan produk, lingkup, dan batasannya |
| [docs/TRACE.md](docs/TRACE.md) | Orang baru yang ingin tahu alur dari browser sampai kembali ke browser |
| [docs/CODE.md](docs/CODE.md) | Pengembang yang akan mengubah kode |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Menerapkan, memperbarui, dan menghapus |
| [CHANGELOG.md](CHANGELOG.md) | Riwayat perubahan beserta alasannya |

---

## Batasan

Proyek ini berstatus **demo**, bukan produk siap pakai.

| Batasan | Keterangan |
|---|---|
| Endpoint tanpa autentikasi | Siapa pun yang tahu alamatnya dapat memanggil dan menimbulkan biaya model |
| Bukti tidak tersimpan permanen | Arsip bukti mati secara bawaan. Nyalakan dengan `azd env set ENABLE_STORAGE true` bila langganan mengizinkan |
| Deteksi foto berulang terbatas | Tanpa arsip, indeks berada di memori dan hilang saat aplikasi mati |
| Hasil bervariasi antarpercobaan | Model keluarga GPT-5 tidak menerima penyetelan `temperature` |
| Belum ada pengujian otomatis | Prioritas pengujian tercantum di docs/CODE.md |

Hal-hal yang **tidak dapat** disimpulkan dari foto, seperti susunan jalan, ukuran dalam satuan, riwayat banjir, kondisi struktur, dan legalitas, sengaja tidak dihasilkan sistem ini.
