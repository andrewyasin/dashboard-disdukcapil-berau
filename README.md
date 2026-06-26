# Dashboard Ulasan — Aplikasi Disdukcapil Berau

Dashboard publik yang menampilkan analisis ulasan pengguna aplikasi
Disdukcapil Kabupaten Berau dari Google Play Store. Data diperbarui
**otomatis setiap hari** melalui GitHub Actions dan ditampilkan via
GitHub Pages — mendukung pemenuhan **Aspek 50303 (Pemanfaatan Big Data)**
pada penilaian EPSS/IPS BPS.

🔗 **Demo:** [andrewyasin.github.io/dashboard-disdukcapil-berau](https://andrewyasin.github.io/dashboard-disdukcapil-berau/)

---

## 🚀 Cara Setup di GitHub (sekali saja)

### 1. Buat repository baru
- Buka [github.com/new](https://github.com/new)
- Nama repo: `dashboard-disdukcapil-berau`
- Set ke **Public** (wajib untuk GitHub Pages gratis)
- Jangan centang "Add README" (sudah ada di sini)

### 2. Upload semua file project ini
```bash
cd dashboard-disdukcapil-berau
git init
git add .
git commit -m "Inisialisasi dashboard ulasan Disdukcapil Berau"
git branch -M main
git remote add origin https://github.com/<username-anda>/dashboard-disdukcapil-berau.git
git push -u origin main
```

### 3. Aktifkan GitHub Pages
- Buka repo di GitHub → **Settings** → **Pages**
- Source: pilih **GitHub Actions** (bukan "Deploy from branch")
- Simpan

### 4. Aktifkan permission Actions
- **Settings** → **Actions** → **General** → scroll ke **Workflow permissions**
- Pilih **Read and write permissions**
- Simpan

### 5. Jalankan workflow pertama kali (manual)
- Buka tab **Actions** di repo
- Pilih workflow **"Update Dashboard Data"**
- Klik **Run workflow** → **Run workflow**
- Tunggu ±1-2 menit hingga selesai (centang hijau)

Setelah itu, dashboard otomatis bisa diakses di:
```
https://<username-anda>.github.io/dashboard-disdukcapil-berau/
```

---

## ⚙️ Cara Kerja Otomatisasi

```
┌─────────────────┐     setiap hari jam 01:00 WITA      ┌──────────────────┐
│  GitHub Actions  │ ──────────────────────────────────▶ │  scripts/scrape.py│
│   (terjadwal)    │                                      │ (scraping Play   │
└─────────────────┘                                      │  Store + olah)   │
                                                            └────────┬─────────┘
                                                                     │
                                                                     ▼
                                                            ┌──────────────────┐
                                                            │  docs/data.json  │
                                                            │ (commit otomatis)│
                                                            └────────┬─────────┘
                                                                     │
                                                                     ▼
                                                            ┌──────────────────┐
                                                            │  GitHub Pages    │
                                                            │  docs/index.html │
                                                            │  (baca data.json)│
                                                            └──────────────────┘
```

1. **Setiap hari pukul 01:00 WITA**, GitHub Actions menjalankan `scripts/scrape.py`
2. Script mengambil ulasan terbaru dari Google Play Store, membersihkan, mengkategorikan, dan menghitung statistik
3. Hasil disimpan sebagai `docs/data.json` dan otomatis di-commit ke repo
4. `docs/index.html` (dashboard) membaca `data.json` tersebut dan menampilkan grafik secara otomatis
5. GitHub Pages men-deploy ulang halaman setiap ada perubahan

Anda **tidak perlu menjalankan apa pun secara manual** setelah setup awal selesai.

---

## 🛠️ Mengubah Jadwal Update

Edit file `.github/workflows/update.yml`, baris:
```yaml
- cron: "0 17 * * *"   # 17:00 UTC = 01:00 WITA
```
Gunakan [crontab.guru](https://crontab.guru) untuk membantu menghitung jadwal (selalu dalam UTC).

## 🔧 Mengubah App ID

Jika App ID aplikasi Disdukcapil Berau berbeda dari yang digunakan saat ini,
edit baris berikut di `scripts/scrape.py`:
```python
APP_ID = "com.disdukcapil.berau"  # ganti sesuai App ID yang benar
```

App ID bisa dilihat dari URL aplikasi di Play Store, contoh:
`https://play.google.com/store/apps/details?id=com.disdukcapil.berau`
→ App ID-nya adalah `com.disdukcapil.berau`

## 🧪 Menjalankan Scraping Secara Lokal (opsional, untuk testing)

```bash
cd scripts
pip install -r requirements.txt
python scrape.py
```
Hasilnya akan tersimpan di `docs/data.json`, lalu buka `docs/index.html`
di browser untuk melihat pratinjau.

---

## 📁 Struktur Project

```
dashboard-disdukcapil-berau/
├── .github/workflows/update.yml   # GitHub Actions: scraping + deploy
├── scripts/
│   ├── scrape.py                  # Script scraping & pengolahan data
│   └── requirements.txt           # Dependensi Python
├── docs/
│   ├── index.html                 # Halaman dashboard (GitHub Pages)
│   ├── chart.umd.min.js           # Library Chart.js (lokal, tanpa CDN)
│   └── data.json                  # Data hasil scraping (auto-update)
└── README.md
```

---

## 📊 Tentang Data

Sumber: ulasan publik aplikasi Disdukcapil Berau di Google Play Store,
diambil melalui `google-play-scraper`. Dashboard ini disusun untuk
mendukung **Pemanfaatan Big Data** sesuai Aspek 50303 EPSS BPS, dengan
karakteristik *Volume* (ratusan ulasan), *Variety* (teks, rating, metadata),
dan *Velocity* (data diperbarui harian secara otomatis).

## 📝 Lisensi

Bebas digunakan dan dimodifikasi untuk keperluan pemerintahan daerah di Indonesia.

Dibuat oleh **Diskominfo Kabupaten Berau** · Kalimantan Timur
