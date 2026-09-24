# Panduan Penerapan

Dokumen ini menjelaskan cara membangun, memperbarui, dan menghapus demo **Asisten Review Bukti Survei Rumah** di Azure.

Untuk memahami cara kerja kodenya, baca [TRACE.md](TRACE.md).
Untuk memahami tujuan produknya, baca [PRD.md](PRD.md).

---

## 1. Ringkasan

| | |
|---|---|
| **Perintah utama** | `azd up` |
| **Region** | Southeast Asia |
| **Resource group** | `rg-survei-demo` |
| **Model** | `gpt-5-mini`, versi `2025-08-07` |
| **Autentikasi** | Managed Identity sepenuhnya, tanpa kunci |
| **Docker lokal** | Tidak diperlukan, image dibangun di ACR |

---

## 2. Prasyarat

| Kebutuhan | Cara memastikan |
|---|---|
| Azure Developer CLI | `azd version` |
| Azure CLI | `az version` |
| Sudah masuk | `azd auth login` dan `az login` |
| Langganan aktif | `az account show` |
| Hak akses | Cukup untuk membuat resource group dan memberikan peran RBAC |

Docker Desktop tidak diperlukan karena `azure.yaml` memakai `remoteBuild: true`, sehingga image dibangun oleh ACR.

---

## 3. Membangun Semuanya

```powershell
cd c:\labs\tech\bcaf27\agentpenlai
azd up
```

Bila lingkungan azd belum ada:

```powershell
azd env new survei-demo --location southeastasia --subscription <id-langganan>
azd up
```

`azd up` menjalankan tiga tahap berurutan:

1. **Provision** — membuat resource group dan seluruh sumber daya dari `infra/`.
2. **Package** — membangun image kontainer di ACR.
3. **Deploy** — menerapkan image ke Container Apps.

Selesai, `azd` menampilkan alamat aplikasi pada baris `SERVICE_WEB_URI`.

---

## 4. Yang Dibuat

Seluruhnya berada di dalam satu resource group.

| Sumber daya | Tingkat | Fungsi |
|---|---|---|
| User-assigned Managed Identity | — | Identitas tunggal untuk seluruh akses antarlayanan |
| AI Services (Foundry) | S0 | Menjalankan model multimodal |
| Model deployment `gpt-5-mini` | GlobalStandard | Ekstraksi data dari foto |
| Azure Maps | Gen2 | Reverse geocode, geocode, rute kendaraan |
| Container Registry | Basic | Menyimpan image aplikasi |
| Container Apps Environment | Consumption | Tempat aplikasi berjalan |
| Container App | Skala 0–1 replika | Aplikasi web dan API |
| Log Analytics | PerGB2018, batas 0,1 GB per hari | Log kontainer |
| Application Insights | — | Telemetri aplikasi |

### Peran yang Diberikan

Semua diberikan kepada satu Managed Identity, pada cakupan masing-masing sumber daya.

| Peran | Cakupan | Keperluan |
|---|---|---|
| `AcrPull` | Container Registry | Menarik image saat kontainer dijalankan |
| `Cognitive Services OpenAI User` | AI Services | Memanggil model |
| `Azure Maps Data Reader` | Azure Maps | Memanggil API peta |

---

## 5. Parameter

Diatur lewat variabel lingkungan azd, tanpa mengubah kode.

| Parameter | Variabel | Nilai bawaan |
|---|---|---|
| Nama model | `AZURE_AI_MODEL_NAME` | `gpt-5-mini` |
| Versi model | `AZURE_AI_MODEL_VERSION` | `2025-08-07` |
| Kapasitas model | parameter Bicep `modelCapacity` | `10` |
| Arsip bukti di Blob Storage | `ENABLE_STORAGE` | `false` |
| Region | `AZURE_LOCATION` | `southeastasia` |

Mengganti model:

```powershell
azd env set AZURE_AI_MODEL_NAME gpt-5.4-mini
azd env set AZURE_AI_MODEL_VERSION 2026-03-17
azd up
```

Melihat model yang tersedia di suatu region:

```powershell
az cognitiveservices model list -l southeastasia --query "[?model.format=='OpenAI'].model.name" -o tsv | Sort-Object -Unique
```

---

## 6. Memperbarui

| Perubahan | Perintah |
|---|---|
| Hanya kode aplikasi | `azd deploy web` |
| Infrastruktur, atau keduanya | `azd up` |

> **Peringatan.** Jangan menjalankan `azd provision` sendirian setelah aplikasi berjalan. Bicep menetapkan image awal sebagai placeholder, sehingga `azd provision` akan mengembalikan Container App ke image contoh dan aplikasi berhenti berfungsi. Pulihkan dengan `azd deploy web`.

---

## 7. Menghapus dan Membangun Ulang

```powershell
azd down --force --purge
```

`--purge` wajib. AI Services memakai penghapusan sementara, dan nama sumber daya pada susunan ini bersifat tetap untuk nama lingkungan yang sama. Tanpa `--purge`, pembuatan ulang akan bentrok dengan nama yang masih tertahan.

Membangun ulang cukup `azd up`. Karena nama bersifat tetap, **alamat aplikasi akan sama seperti sebelumnya**.

---

## 8. Verifikasi

```powershell
curl.exe -s "<alamat-aplikasi>/api/health"
```

Keluaran yang diharapkan:

```json
{"aiConfigured":true,"mapsConfigured":true,"storageConfigured":false,"deployment":"gpt-5-mini"}
```

| Ruas | Arti |
|---|---|
| `aiConfigured` | Endpoint dan nama deployment model terbaca |
| `mapsConfigured` | Client id Azure Maps terbaca |
| `storageConfigured` | Selalu `false` pada demo, lihat §9 |
| `deployment` | Nama deployment model yang dipakai |

Panggilan pertama bisa memakan waktu lebih dari satu menit karena replika berskala nol dan harus dinyalakan lebih dulu.

Menguji alur penuh:

```powershell
curl.exe -s -m 300 -X POST "<alamat-aplikasi>/api/review" `
  --form-string "caseId=DEMO-001" `
  --form-string "latitude=-7.6689" `
  --form-string "longitude=109.6519" `
  --form-string "claimedAddress=Jalan Pahlawan, Kebumen" `
  --form-string "requiredPhotos=tampak-depan" `
  -F "photos=@foto.jpg"
```

---

## 9. Kendala yang Sudah Ditemukan

Empat hal berikut ditemukan saat penerapan pertama dan **sudah diperbaiki di kode**. Dicatat agar tidak terulang.

### 9.1 Blob Storage Diblokir Policy

Storage account dibuat dengan `publicNetworkAccess` bernilai `Disabled`, dan **tetap `Disabled` meski Bicep menyetelnya `Enabled`**. Ini ditegakkan oleh Azure Policy di tingkat yang lebih tinggi dari langganan.

**Akibatnya:** Blob Storage **mati secara bawaan**, dan arsip bukti dilewati.

| Konsekuensi | Penjelasan |
|---|---|
| Bukti tidak tersimpan permanen | Foto hanya diproses, tidak diarsipkan |
| Deteksi foto berulang terbatas | Indeks disimpan di memori dan hilang saat aplikasi mati |

### Menyalakan Arsip Bukti

Di langganan yang **tidak** menerapkan policy tersebut, fiturnya dapat dinyalakan tanpa mengubah kode:

```powershell
azd env set ENABLE_STORAGE true
azd up
```

Penerapan akan membuat storage account, kontainer `bukti`, peran `Storage Blob Data Contributor`, serta mengisi variabel `AZURE_STORAGE_ACCOUNT_URL` dan `AZURE_STORAGE_CONTAINER` pada aplikasi. Kode di `storage.py` mengenalinya secara otomatis.

Pastikan dengan memanggil `/api/health` dan melihat `storageConfigured` bernilai `true`.

> **Catatan.** Setelah dinyalakan, tunggu beberapa menit sebelum menguji. Peran data plane pada Storage memerlukan waktu untuk menyebar, dan sebelum itu panggilan akan ditolak dengan `AuthorizationFailure`.

Untuk tetap memakainya di langganan yang menerapkan policy, diperlukan private endpoint dengan Container Apps terintegrasi VNet, dan biayanya lebih tinggi.

### 9.2 Model Menolak `temperature`

Model keluarga GPT-5 hanya menerima nilai bawaan. Mengirim `temperature=0` menghasilkan galat 400.

**Akibatnya:** parameter tersebut dihapus dari pemanggilan. Hasil bisa sedikit berbeda antarpercobaan meski masukannya sama.

### 9.3 Tag Base Image

`mcr.microsoft.com/devcontainers/python:3.12-bookworm-slim` tidak ada. Sekarang memakai `mcr.microsoft.com/azurelinux/base/python`, yang lebih ringan dan tidak terkena batas tarik Docker Hub.

### 9.4 Upgrade pip Gagal

pip bawaan pada Azure Linux dipasang lewat rpm sehingga tidak dapat ditimpa. Langkah upgrade pip dihapus dari `Dockerfile`.

---

## 10. Biaya

| Pos | Sifat |
|---|---|
| Container Apps | Berskala nol, tidak ditagih saat menganggur |
| AI Services | Per token |
| Azure Maps | Per panggilan |
| Container Registry Basic | Biaya tetap kecil |
| Log Analytics | Dibatasi 0,1 GB per hari |

Satu-satunya biaya tetap yang berarti adalah Container Registry. Jalankan `azd down --force --purge` bila demo sudah selesai.

---

## 11. Melacak Masalah

```powershell
# log kontainer
az containerapp logs show -n <nama-container-app> -g rg-survei-demo --tail 50 --type console

# status revisi
az containerapp revision list -n <nama-container-app> -g rg-survei-demo -o table

# memastikan peran sudah diberikan
$mi = az identity list -g rg-survei-demo --query "[0].principalId" -o tsv
az role assignment list --assignee $mi --all -o table
```

| Gejala | Kemungkinan sebab |
|---|---|
| `This request is not authorized` | Peran belum menyebar, tunggu beberapa menit |
| Halaman menampilkan aplikasi contoh | `azd provision` mengembalikan image, jalankan `azd deploy web` |
| Galat 400 dari model | Parameter tidak didukung model, periksa pesan galatnya |
| Panggilan pertama sangat lambat | Replika sedang dinyalakan dari nol |
