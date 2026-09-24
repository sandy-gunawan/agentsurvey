# Dokumentasi Kode

Referensi teknis untuk pengembang yang akan membaca, mengubah, atau memperluas kode ini.

- Alur permintaan dari ujung ke ujung: [TRACE.md](TRACE.md)
- Cara menerapkan: [DEPLOYMENT.md](DEPLOYMENT.md)
- Tujuan produk dan batasannya: [PRD.md](PRD.md)

---

## 1. Struktur Proyek

```
azure.yaml                          Konfigurasi azd
infra/
  main.bicep                        Lingkup langganan, membuat resource group
  resources.bicep                   Seluruh sumber daya, lingkup resource group
  main.parameters.json              Pemetaan variabel azd ke parameter Bicep
src/
  Dockerfile                        Image kontainer
  requirements.txt                  Dependensi Python
  app/
    main.py                         Rute FastAPI dan orkestrasi
    config.py                       Konfigurasi dari variabel lingkungan
    auth.py                         Kredensial dan token
    maps.py                         Klien Azure Maps
    vision.py                       Klien model multimodal
    rules.py                        Aturan rekomendasi
    hashing.py                      Sidik gambar dan pengecilan ukuran
    storage.py                      Penyimpanan bukti
    prompts/system_prompt.txt       Instruksi dan skema keluaran model
    static/                         index.html, app.js, styles.css
docs/                               PRD, TRACE, DEPLOYMENT, CODE
```

---

## 2. Prinsip Rancangan

| Prinsip | Wujudnya dalam kode |
|---|---|
| Satu tempat untuk tiap tanggung jawab | `main.py` tidak memanggil Azure langsung; semua panggilan keluar ada di `maps.py` dan `vision.py` |
| Tanpa rahasia | Tidak ada kunci maupun connection string; seluruh akses lewat `auth.py` |
| Keputusan tetap pada aturan | Model hanya mengisi temuan; rekomendasi dihasilkan `rules.py` |
| Gagal sebagian tetap berguna | Kegagalan peta dan penyimpanan tidak menggugurkan permintaan |
| Batas produk ditulis di kode | `creditDecision` dan `propertyValue` selalu `None` |
| Konfigurasi bukan konstanta tersebar | Seluruh ambang ada di `config.py` |

---

## 3. Referensi Modul

### 3.1 `config.py`

Satu kelas `Settings`, dibuat sekali sebagai `settings` pada tingkat modul.

| Atribut | Variabel lingkungan | Bawaan |
|---|---|---|
| `ai_endpoint` | `AZURE_AI_ENDPOINT` | `""` |
| `ai_deployment` | `AZURE_AI_DEPLOYMENT` | `""` |
| `ai_api_version` | `AZURE_AI_API_VERSION` | `2024-12-01-preview` |
| `maps_client_id` | `AZURE_MAPS_CLIENT_ID` | `""` |
| `maps_base_url` | `AZURE_MAPS_BASE_URL` | `https://atlas.microsoft.com` |
| `storage_account_url` | `AZURE_STORAGE_ACCOUNT_URL` | `""` |
| `storage_container` | `AZURE_STORAGE_CONTAINER` | `bukti` |
| `managed_identity_client_id` | `AZURE_CLIENT_ID` | `""` |
| `address_match_radius_m` | `ADDRESS_MATCH_RADIUS_M` | `150` |
| `gang_snap_threshold_m` | `GANG_SNAP_THRESHOLD_M` | `30` |
| `duplicate_threshold` | `DUPLICATE_THRESHOLD` | `5` |

Dua properti turunan:

```python
settings.maps_enabled      # bool(maps_client_id)
settings.storage_enabled   # bool(storage_account_url)
```

Keduanya dipakai sebagai sakelar fitur. Bila `AZURE_STORAGE_ACCOUNT_URL` kosong, seluruh jalur penyimpanan dilewati tanpa galat.

---

### 3.2 `auth.py`

```python
get_credential() -> DefaultAzureCredential
get_cognitive_token_provider() -> Callable[[], str]
get_maps_token() -> str
```

| Hal | Penjelasan |
|---|---|
| `lru_cache(maxsize=1)` | Kredensial dan penyedia token dibuat sekali seumur proses |
| Pemilihan identitas | Bila `AZURE_CLIENT_ID` terisi, dipakai sebagai `managed_identity_client_id`; bila kosong, jatuh ke identitas `az login` |
| Dua scope | `cognitiveservices.azure.com` untuk model, `atlas.microsoft.com` untuk peta |

Kode ini tidak perlu diubah saat berpindah antara komputer lokal dan Azure.

---

### 3.3 `hashing.py`

```python
HASH_SIZE = 8

average_hash(data: bytes) -> str          # 64 bit, 16 digit heksadesimal
hamming(a: str, b: str) -> int            # jumlah bit berbeda
downscale(data: bytes, max_side: int = 1024) -> bytes
```

`average_hash` memakai algoritma aHash: ubah ke abu-abu, perkecil menjadi 8×8, bandingkan tiap piksel dengan rata-rata.

`downscale` menghasilkan JPEG mutu 80 dengan sisi terpanjang 1024 piksel, dipakai sebelum gambar dikirim ke model.

> **Batasan.** aHash peka terhadap pemotongan, perputaran, dan perubahan pencahayaan. Untuk produksi, pHash atau dHash lebih tahan.

---

### 3.4 `maps.py`

Seluruh fungsi publik bersifat asinkron dan memakai `httpx.AsyncClient`.

```python
haversine_m(lat1, lon1, lat2, lon2) -> float

async reverse_geocode(client, lat, lon) -> dict
# {"address": str|None, "street": str|None, "roadUse": list[str]}

async geocode(client, address) -> tuple[float, float] | None

async car_snap(client, lat, lon, origin) -> dict
# {"snapDistanceMeter": int|None, "carAccessible": "ya"|"tidak"|"tidak_dapat_ditentukan"}

async analyse_location(lat, lon, claimed_address) -> dict
```

Bentuk keluaran `analyse_location`:

| Ruas | Tipe | Keterangan |
|---|---|---|
| `reverseGeocodedAddress` | `str \| None` | Alamat hasil pembacaan balik |
| `nearestStreet` | `str \| None` | Nama jalan terdekat |
| `roadUse` | `list[str]` | Kategori jalan dari Azure Maps |
| `onMainRoad` | `"ya" \| "tidak" \| "tidak_dapat_ditentukan"` | Irisan dengan `MAIN_ROAD_USES` |
| `addressMatch` | empat nilai | Berdasarkan jarak, lihat tabel di bawah |
| `addressDistanceMeter` | `int \| None` | Jarak koordinat ke alamat pengajuan |
| `snapDistanceMeter` | `int \| None` | Jarak ke titik terdekat yang dapat dicapai mobil |
| `carAccessible` | tiga nilai | Dibandingkan dengan `gang_snap_threshold_m` |
| `mapCoverageLimited` | `bool` | Benar bila alamat tidak ditemukan |

Ambang kecocokan alamat:

| Jarak | Hasil |
|---|---|
| ≤ 150 m | `cocok` |
| ≤ 750 m | `cocok_sebagian` |
| > 750 m | `tidak_cocok` |

**Endpoint yang dipanggil**

| Fungsi | Endpoint | Versi API |
|---|---|---|
| `reverse_geocode` | `/search/address/reverse/json` | `1.0` |
| `geocode` | `/search/address/json` | `1.0` |
| `car_snap` | `/route/directions/json` | `1.0` |

`reverse_geocode` memakai `returnRoadUse=true` untuk memperoleh kategori jalan.

**Penanganan galat**

| Fungsi | Perilaku |
|---|---|
| `reverse_geocode`, `geocode` | `raise_for_status()`, galat dilempar ke atas |
| `car_snap` | Status ≥ 400 dikembalikan sebagai `tidak_dapat_ditentukan`, tidak melempar |

Pemanggil di `main.py` membungkus seluruhnya dalam `try`, sehingga kegagalan peta tidak menggugurkan permintaan.

> **Titik asal rute.** Bila `claimed_address` kosong, titik asal diambil dari `ROUTE_PROBE_OFFSET_DEG`, yaitu pergeseran 0,01 derajat atau sekitar 1,1 km. Nilainya tidak penting selama cukup jauh, karena yang dipakai hanya titik akhir rute. Konstanta ini berada di `maps.py`.

---

### 3.5 `vision.py`

```python
SYSTEM_PROMPT: str   # dibaca dari prompts/system_prompt.txt saat modul dimuat

_client() -> AzureOpenAI
_image_part(data: bytes) -> dict

extract_findings(
    photos: list[tuple[str, bytes]],
    claimed_address: str,
    map_result: dict,
    required_photos: list[str],
    missing_photos: list[str],
) -> dict
```

Susunan pesan yang dikirim:

1. Satu blok teks berisi konteks JSON: alamat pengajuan, hasil peta, daftar foto wajib, foto yang belum ada, nama berkas terlampir.
2. Untuk tiap foto: satu blok teks berisi nama berkas, lalu satu blok gambar.

Nama berkas disebut sebelum gambarnya **agar model dapat merujuk foto sumber pada `evidenceRefs`**.

Parameter pemanggilan:

| Parameter | Nilai | Alasan |
|---|---|---|
| `response_format` | `{"type": "json_object"}` | Memaksa keluaran JSON |
| `detail` pada gambar | `"low"` | Menekan jumlah token gambar |
| `temperature` | **tidak dikirim** | Model keluarga GPT-5 menolak nilai selain bawaan |

> **Jangan menambahkan `temperature`.** Model akan mengembalikan galat 400.

> **Balasan tidak sah.** Bila model mengembalikan JSON yang tidak dapat diurai, fungsi melempar `ValueError` beserta 200 karakter pertama balasannya, sehingga penyebabnya terlihat di log.

---

### 3.6 `rules.py`

```python
build_recommendation(
    missing_photos: list[str],
    findings: dict,
    location: dict,
    duplicates: list[dict],
) -> dict
# {"action": str, "reasons": list[str]}
```

Fungsi murni: tidak memanggil apa pun dan tidak menyimpan keadaan. Mudah diuji.

Urutan keputusan:

1. Kumpulkan `reasons`, yaitu hal yang membuat bukti kurang.
2. Kumpulkan `needs_visit`, yaitu hal yang menuntut kunjungan.
3. Bila `needs_visit` tidak kosong, hasilnya `perlu_kunjungan`.
4. Bila hanya `reasons` yang terisi, hasilnya `perlu_bukti_tambahan`.
5. Bila keduanya kosong, hasilnya `lengkap`.

| Pemicu `perlu_kunjungan` | Sumber |
|---|---|
| `addressMatch == "tidak_cocok"` | `location` |
| Ada foto serupa di berkas lain | `duplicates` |
| `mapCoverageLimited` benar | `location` |
| `forSaleSign == "ada"` | `findings` |

| Pemicu `perlu_bukti_tambahan` | Sumber |
|---|---|
| Ada foto wajib yang belum ada | `missing_photos` |
| Lebih dari separuh bidang bernilai `tidak_dapat_dinilai` | `findings` |
| Ada foto dengan masalah mutu | `findings.photoQuality` |

> **Aturan tidak boleh dipindahkan ke model.** Bagian ini harus dapat dibaca dan diaudit manusia.

---

### 3.7 `storage.py`

```python
load_index() -> list[dict]
append_index(entries: list[dict]) -> bool
save_photo(case_id: str, filename: str, data: bytes) -> bool
save_result(case_id: str, result: dict) -> bool
```

| Sifat | Penjelasan |
|---|---|
| Tidak pernah melempar galat | Semua fungsi mengembalikan `bool` |
| Dua mode | Blob Storage bila dikonfigurasi, `_memory_index` bila tidak |
| Nilai balik saat nonaktif | `True`, karena tidak ada kegagalan |

Tata letak blob:

```
<caseId>/<nama-foto>
<caseId>/hasil.json
index/hashes.json
```

> **Status saat ini.** Arsip bukti **mati secara bawaan**. Nyalakan dengan `azd env set ENABLE_STORAGE true` lalu `azd up`, selama langganan mengizinkan akses jaringan publik pada storage. Lihat DEPLOYMENT.md §9.1.

> **Batasan.** `append_index` membaca seluruh indeks lalu menulisnya kembali. Tidak aman bila ada penulisan bersamaan, dan tidak dapat diskalakan. Untuk produksi, gunakan basis data.

---

### 3.8 `main.py`

```python
GET  /              -> index.html
GET  /api/health    -> status konfigurasi
POST /api/review    -> pemrosesan utama
```

Konstanta ambang berada di `config.py`, bukan tersebar di modul ini.

Urutan di dalam `review()`:

| Urutan | Kegiatan | Sifat |
|---|---|---|
| 1 | Validasi konfigurasi | Gagal cepat |
| 2 | Baca berkas dan hitung sidik | Sinkron, di memori |
| 3 | Cocokkan dengan daftar foto wajib | Pencocokan potongan nama |
| 4 | Cari foto serupa | O(n×m) terhadap indeks |
| 5 | Analisis lokasi | Asinkron, dibungkus `try` |
| 6 | Panggil model | Sinkron, dibungkus `asyncio.to_thread` |
| 7 | Susun rekomendasi | Fungsi murni |
| 8 | Rakit hasil | — |
| 9 | Simpan | Tidak pernah melempar galat |

**Model konkurensi.** Pustaka OpenAI bersifat sinkron. Memanggilnya langsung di fungsi `async` akan memblokir event loop, sehingga dibungkus:

```python
findings = await asyncio.to_thread(vision.extract_findings, ...)
```

`httpx.AsyncClient` di `maps.py` sudah asinkron, jadi tidak perlu perlakuan khusus.

---

## 4. Kontrak Keluaran

Bentuk balasan `POST /api/review`:

| Ruas | Asal |
|---|---|
| `caseId`, `processedAt`, `modelDeployment` | `main.py` |
| `evidence.photoCount`, `evidence.photos`, `evidence.coordinate` | `main.py` dan `hashing.py` |
| `buildingFindings`, `evidenceRefs`, `photoQuality`, `observations`, `cannotAssess`, `notes` | Model, lewat `vision.py` |
| `locationFindings` | `maps.py` |
| `integrityFlags.similarPhotoCases` | `main.py` |
| `missingEvidence` | `main.py` |
| `recommendation` | `rules.py` |
| `creditDecision`, `propertyValue` | Selalu `None` |
| `storageWarning` | Hanya muncul bila penyimpanan gagal |

Skema `buildingFindings` ditetapkan di `prompts/system_prompt.txt`, bukan di kode Python. **Mengubah bidang berarti mengubah prompt.**

---

## 5. Cara Memperluas

### 5.1 Menambah Bidang Temuan Baru

| Langkah | Berkas |
|---|---|
| 1. Tambahkan ke skema JSON dalam prompt, sertakan opsi `tidak_dapat_dinilai` | `prompts/system_prompt.txt` |
| 2. Tambahkan label tampilannya | `static/app.js`, objek `LABELS` |
| 3. Bila memengaruhi rekomendasi, tambahkan aturannya | `rules.py` |

Tidak perlu mengubah `main.py`, karena `buildingFindings` diteruskan apa adanya.

### 5.2 Menambah Aturan Rekomendasi

Cukup satu berkas: `rules.py`. Tambahkan ke `needs_visit` atau `reasons`.

### 5.3 Menambah Sinyal Lokasi

| Langkah | Berkas |
|---|---|
| 1. Tambahkan fungsi pemanggil endpoint | `maps.py` |
| 2. Sertakan hasilnya pada `analyse_location` | `maps.py` |
| 3. Tambahkan label tampilannya | `static/app.js` |

### 5.4 Mengubah Ambang

Lewat variabel lingkungan, tanpa menyentuh kode:

```powershell
azd env set ADDRESS_MATCH_RADIUS_M 200
azd env set GANG_SNAP_THRESHOLD_M 40
azd env set DUPLICATE_THRESHOLD 8
azd up
```

Seluruh ambang berada di `config.py` dan dapat diatur lewat variabel lingkungan.

---

## 6. Pengembangan Lokal

Selalu memakai virtual environment.

```powershell
cd c:\labs\tech\bcaf27\agentpenlai\src
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ambil nilai konfigurasi dari lingkungan azd:

```powershell
azd env get-values
```

Setel yang diperlukan, lalu jalankan. **Jangan menyetel `AZURE_CLIENT_ID`** agar kredensial jatuh ke identitas `az login`:

```powershell
$env:AZURE_AI_ENDPOINT = "https://<subdomain>.openai.azure.com/"
$env:AZURE_AI_DEPLOYMENT = "gpt-5-mini"
$env:AZURE_MAPS_CLIENT_ID = "<uniqueId akun Maps>"
uvicorn app.main:app --reload --port 8000
```

Identitas `az login` memerlukan peran yang sama seperti Managed Identity: `Cognitive Services OpenAI User` dan `Azure Maps Data Reader`. Peran ini tidak diberikan otomatis oleh penerapan dan harus ditambahkan sendiri bila ingin menjalankan lokal.

---

## 7. Dependensi

| Paket | Keperluan |
|---|---|
| `fastapi` | Kerangka web dan validasi masukan |
| `uvicorn[standard]` | Server ASGI |
| `python-multipart` | Membaca unggahan `multipart/form-data` |
| `azure-identity` | Managed Identity dan token |
| `azure-storage-blob` | Penyimpanan bukti, saat ini nonaktif |
| `openai` | Klien model, dipakai dengan endpoint Azure |
| `httpx` | Klien HTTP asinkron untuk Azure Maps |
| `Pillow` | Sidik gambar dan pengecilan ukuran |
| `pydantic` | Dependensi FastAPI |

Versi dikunci di `requirements.txt`.

---

## 8. Referensi Infrastruktur

`infra/main.bicep` berada pada lingkup langganan dan hanya membuat resource group lalu memanggil `resources.bicep`.

Penamaan sumber daya:

```bicep
var token = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var prefix = take(replace(toLower(environmentName), '-', ''), 12)
```

Karena ketiga masukan tetap, **nama sumber daya juga tetap** untuk nama lingkungan yang sama. Inilah sebabnya `azd down` memerlukan `--purge`, dan sebabnya alamat aplikasi tidak berubah setelah dibangun ulang.

Titik yang perlu diperhatikan saat mengubah Bicep:

| Hal | Catatan |
|---|---|
| Nama storage account | Dibatasi 24 karakter; sudah dipotong dengan `take()` |
| Versi model | `union()` dipakai agar versi dapat dikosongkan |
| Image awal Container App | Placeholder; `azd deploy` yang menggantinya |
| `maxReplicas: 1` | Disengaja, karena indeks sidik berada di memori |
| Pemberian peran | Pada lingkup masing-masing sumber daya, bukan resource group |

---

## 9. Utang Teknis dan Batasan

### 9.1 Keamanan

| Masalah | Dampak |
|---|---|
| **`POST /api/review` tidak terlindungi autentikasi** | Siapa pun yang tahu alamatnya dapat memanggil dan menimbulkan biaya model |
| Tidak ada pembatasan laju | Rentan terhadap penyalahgunaan |
| Tidak ada batas ukuran atau jumlah foto | Permintaan besar dapat menghabiskan memori |

**Ketiganya dapat diterima untuk demo tertutup, tetapi wajib ditangani sebelum dipakai di luar itu.**

### 9.2 Ketepatan

| Masalah | Dampak |
|---|---|
| aHash lemah terhadap pemotongan dan perputaran | Foto yang dipakai ulang bisa lolos |
| Pencocokan foto wajib memakai potongan nama | Rentan salah cocok |
| Titik asal rute memakai pergeseran sembarang | Hasil `snapDistanceMeter` bisa menyesatkan bila alamat pengajuan kosong |
| Hasil model bervariasi antarpercobaan | `temperature` tidak dapat disetel |

### 9.3 Skala

| Masalah | Dampak |
|---|---|
| Indeks sidik di memori | Hilang saat aplikasi mati, tidak dapat dibagi antarreplika |
| `_find_duplicates` berjalan O(n×m) | Melambat seiring bertambahnya berkas |
| `append_index` baca-tulis seluruh indeks | Tidak aman bila bersamaan |

### 9.4 Kebersihan Kode

Seluruh butir yang sebelumnya tercatat di bagian ini sudah dibereskan: kode mati dihapus, ambang dipindahkan ke `config.py`, penangkapan galat dipersempit ke `ResourceExistsError`, titik asal rute diberi nama, dan balasan model yang tidak sah kini melempar `ValueError` dengan pesan yang jelas.

Yang tersisa hanya soal gaya penulisan, bukan cacat.

### 9.5 Pengujian

**Belum ada pengujian otomatis sama sekali.** Prioritas bila akan ditambahkan:

| Prioritas | Sasaran | Alasan |
|---|---|---|
| 1 | `rules.build_recommendation` | Fungsi murni, paling mudah diuji, paling berisiko bila salah |
| 2 | `hashing.average_hash` dan `hamming` | Deterministik |
| 3 | `maps.analyse_location` | Perlu tiruan respons HTTP |
| 4 | Penjaga `creditDecision` dan `propertyValue` selalu `None` | Batas produk |

---

## 10. Pantangan

| Jangan | Alasan |
|---|---|
| Menambahkan `temperature` pada panggilan model | Ditolak model keluarga GPT-5 |
| Memindahkan logika rekomendasi ke model | Harus dapat diaudit |
| Mengisi `creditDecision` atau `propertyValue` | Batas produk yang disengaja |
| Menambah bidang tanpa opsi `tidak_dapat_dinilai` | Memaksa model menebak |
| Menaikkan `maxReplicas` sebelum indeks dipindah ke penyimpanan bersama | Deteksi foto berulang menjadi tidak konsisten |
| Menjalankan `azd provision` sendirian setelah aplikasi berjalan | Image kembali ke placeholder |
| Memakai EXIF sebagai sumber koordinat tepercaya | Mudah disunting dan kerap terhapus |
