"""
Scraping ulasan aplikasi Disdukcapil Berau dari Google Play Store.
Dijalankan otomatis setiap hari oleh GitHub Actions.

Output (semua di folder docs/):
  - data.json            : agregat untuk dashboard web (skema TIDAK berubah)
  - reviews.csv          : SEMUA ulasan, satu baris per ulasan (untuk Power BI)
  - review_kategori.csv  : tabel jembatan ulasan -> kategori (satu ulasan bisa banyak kategori)
  - kategori_lengkap.csv : sama, tetapi membawa atribut ulasan (untuk Looker Studio)

Catatan privasi: nama pengguna TIDAK diekspor ke CSV.
reviews.csv bersifat akumulatif: ulasan yang sudah pernah terambil tetap disimpan
walaupun nanti dihapus pengguna dari Play Store.
"""

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta

import pandas as pd

# ── KONFIGURASI ──────────────────────────────────────────────────────────────
APP_ID = "com.disdukcapil.berau"
OUT_DIR = "docs"
OUTPUT_PATH = f"{OUT_DIR}/data.json"
REVIEWS_CSV = f"{OUT_DIR}/reviews.csv"
KATEGORI_CSV = f"{OUT_DIR}/review_kategori.csv"
KATEGORI_LENGKAP_CSV = f"{OUT_DIR}/kategori_lengkap.csv"
MAX_REVIEWS = 1000
WITA = timezone(timedelta(hours=8))

# ── KAMUS KATEGORI ───────────────────────────────────────────────────────────
KATEGORI_KEYWORDS = {
    "KTP / e-KTP": ["ktp", "e-ktp", "ktp digital", "kartu tanda penduduk", "nik"],
    "Akta Kelahiran": ["akta", "akte", "kelahiran", "lahir", "bayi", "anak"],
    "Kartu Keluarga": ["kk", "kartu keluarga", "anggota", "rumah tangga"],
    "Kecepatan Proses": [
        "lama", "lambat", "cepat", "lelet", "tunggu", "antri",
        "proses", "menunggu", "nunggu", "instan", "segera", "kilat",
    ],
    "Kemudahan Aplikasi": [
        "mudah", "susah", "ribet", "bingung", "sulit", "gampang",
        "simpel", "fitur", "menu", "tampilan", "navigasi", "ux",
        "memudahkan", "mempermudah", "permudah", "dimudahkan",
    ],
    "Error / Bug": [
        "error", "crash", "bug", "tidak bisa", "gagal", "force close",
        "loading", "macet", "blank", "kosong", "masalah", "kendala", "eror",
    ],
    "Pelayanan": [
        "pelayanan", "petugas", "staff", "layanan", "respon",
        "bantuan", "admin", "cs", "customer service", "call center",
    ],
    "Dokumen": ["dokumen", "berkas", "persyaratan", "syarat", "upload", "foto", "scan", "file"],
    "Pujian Umum": [
        "bagus", "baik", "mantap", "keren", "membantu", "top", "hebat",
        "sangat baik", "terbaik", "solusi", "inovasi", "bermanfaat", "rekomendasi",
    ],
    "Login / Akun": [
        "login", "akun", "daftar", "registrasi", "kata sandi", "password",
        "gagal masuk", "susah masuk", "sulit masuk", "tidak bisa masuk",
    ],
    "Update / Versi": ["update", "versi", "perbarui", "pembaharuan"],
    "Keluhan Umum": [
        "jelek", "buruk", "payah", "parah", "kecewa", "receh", "tidak bagus",
        "tidak baik", "tidak puas", "becus",
    ],
}

# Kategori yang bermakna positif: tidak boleh terpicu bila didahului negasi
KATEGORI_POSITIF = {"Pujian Umum"}
NEGASI = r"(?:tidak|tak|kurang|belum|gak|ga|nggak|bukan|kok)"


def _pola(kw: str) -> re.Pattern:
    """Kata <=3 huruf dicocokkan utuh (hindari 'nik' di 'elektronik', 'top' di 'stop').
    Kata lebih panjang dicocokkan dari awal kata, sehingga 'proses' tetap cocok
    dengan 'prosesnya'."""
    esc = re.escape(kw)
    if len(kw) <= 3:
        return re.compile(rf"\b{esc}\b")
    return re.compile(rf"\b{esc}")


def _pola_negasi(kw: str) -> re.Pattern:
    return re.compile(rf"\b{NEGASI}\s+(?:\w+\s+)?{re.escape(kw)}")


POLA = {k: [(_pola(kw), _pola_negasi(kw)) for kw in kws] for k, kws in KATEGORI_KEYWORDS.items()}


def label_sentimen(score: int) -> str:
    """Sentimen berbasis rating bintang (BUKAN analisis teks)."""
    if score >= 4:
        return "Positif"
    if score == 3:
        return "Netral"
    return "Negatif"


def daftar_kategori(teks) -> list:
    if not isinstance(teks, str) or not teks.strip():
        return ["Lainnya"]
    t = teks.lower()
    hasil = []
    for kat, pola_list in POLA.items():
        for p, p_neg in pola_list:
            if p.search(t):
                if kat in KATEGORI_POSITIF and p_neg.search(t):
                    continue
                hasil.append(kat)
                break
    return hasil if hasil else ["Lainnya"]


def kategorisasi(teks) -> str:
    return ", ".join(daftar_kategori(teks))


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float) and (pd.isna(obj) or obj in (float("inf"), float("-inf"))):
        return None
    if not isinstance(obj, (list, dict)) and pd.isna(obj):
        return None
    return obj


def bangun_tabel_ulasan(df: pd.DataFrame) -> pd.DataFrame:
    """Ubah hasil scraping mentah menjadi tabel ulasan bersih (tanpa nama pengguna)."""
    out = pd.DataFrame()
    out["review_id"] = df["reviewId"]
    out["tanggal"] = pd.to_datetime(df["at"], errors="coerce")
    out["bintang"] = df["score"].astype(int)
    out["sentimen"] = out["bintang"].apply(label_sentimen)
    out["kategori"] = df["content"].apply(kategorisasi)
    out["isi"] = df["content"].str.replace(r"\s+", " ", regex=True).str.strip()
    out["jumlah_kata"] = out["isi"].str.split().str.len()
    out["likes"] = df["thumbsUpCount"].fillna(0).astype(int)
    out["versi"] = df["reviewCreatedVersion"]
    out["ada_balasan"] = df["replyContent"].notna()
    out["tanggal_balasan"] = pd.to_datetime(df.get("repliedAt"), errors="coerce")
    out["hari_balas"] = (out["tanggal_balasan"] - out["tanggal"]).dt.total_seconds() / 86400
    out["hari_balas"] = out["hari_balas"].round(1)
    out["isi_balasan"] = df["replyContent"]
    out["tahun"] = out["tanggal"].dt.year
    return out


def lengkapi_turunan(df: pd.DataFrame) -> pd.DataFrame:
    """Hitung ulang SEMUA kolom turunan dari kolom dasar (isi, bintang, tanggal, ada_balasan).
    Dipanggil setelah penggabungan arsip, sehingga ulasan lama otomatis mengikuti kamus
    kategori terbaru dan kolom baru selalu terisi."""
    df = df.copy()
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")
    df["tanggal_balasan"] = pd.to_datetime(df["tanggal_balasan"], errors="coerce")
    df["ada_balasan"] = df["ada_balasan"].astype(bool)
    df["sentimen"] = df["bintang"].astype(int).apply(label_sentimen)
    df["kategori"] = df["isi"].apply(kategorisasi)
    df["jumlah_kata"] = df["isi"].fillna("").str.split().str.len()
    df["tahun"] = df["tanggal"].dt.year
    # Kolom ramah Looker Studio: tanggal murni, awal bulan, dan penanda numerik 1/0
    df["tanggal_date"] = df["tanggal"].dt.strftime("%Y-%m-%d")
    df["bulan"] = df["tanggal"].dt.strftime("%Y-%m-01")
    df["status_balasan"] = df["ada_balasan"].map({True: "Dibalas", False: "Belum dibalas"})
    df["dibalas"] = df["ada_balasan"].astype(int)
    df["is_positif"] = (df["sentimen"] == "Positif").astype(int)
    df["is_negatif"] = (df["sentimen"] == "Negatif").astype(int)
    df["skor_sentimen"] = df["is_positif"] - df["is_negatif"]  # rata-ratanya = net sentiment
    df["negatif_dibalas"] = ((df["sentimen"] == "Negatif") & df["ada_balasan"]).astype(int)
    kolom = [
        "review_id", "tanggal", "tanggal_date", "bulan", "tahun", "bintang", "sentimen",
        "is_positif", "is_negatif", "skor_sentimen", "kategori", "isi", "jumlah_kata",
        "likes", "versi", "ada_balasan", "status_balasan", "dibalas", "negatif_dibalas",
        "tanggal_balasan", "hari_balas", "isi_balasan",
    ]
    return df[kolom]


def tabel_kategori_lengkap(df: pd.DataFrame) -> pd.DataFrame:
    """Satu baris per (ulasan, kategori), lengkap dengan atribut ulasan.
    Dipakai sebagai sumber data tersendiri di Looker Studio (tanpa perlu relasi/blend)."""
    out = df[["review_id", "kategori", "tanggal_date", "bulan", "tahun", "bintang",
              "sentimen", "is_positif", "is_negatif", "dibalas"]].copy()
    out["kategori"] = out["kategori"].str.split(", ")
    return out.explode("kategori").reset_index(drop=True)


def gabung_dengan_arsip(baru: pd.DataFrame) -> pd.DataFrame:
    """Gabungkan dengan reviews.csv lama agar ulasan yang pernah terambil tidak hilang."""
    if os.path.exists(REVIEWS_CSV):
        lama = pd.read_csv(REVIEWS_CSV, encoding="utf-8-sig")  # tahan BOM maupun tanpa BOM
        lama = lama[[c for c in baru.columns if c in lama.columns]]  # hanya kolom dasar yang sama
        gabung = pd.concat([lama, baru], ignore_index=True)
        gabung = gabung.drop_duplicates(subset=["review_id"], keep="last")  # data terbaru menang
    else:
        gabung = baru
    gabung = lengkapi_turunan(gabung)
    return gabung.sort_values("tanggal", ascending=False).reset_index(drop=True)


def main() -> None:
    from google_play_scraper import Sort, app, reviews  # impor di sini agar fungsi lain bisa diuji offline

    now_wita = datetime.now(WITA)
    print(f"[{now_wita.strftime('%Y-%m-%d %H:%M WITA')}] Mulai scraping aplikasi: {APP_ID}")
    os.makedirs(OUT_DIR, exist_ok=True)

    info = app(APP_ID, lang="id", country="id")
    result, _ = reviews(
        APP_ID, lang="id", country="id", sort=Sort.NEWEST,
        count=MAX_REVIEWS, filter_score_with=None,
    )
    mentah = pd.DataFrame(result)
    print(f"Berhasil mengambil {len(mentah)} review mentah")

    mentah = mentah.drop_duplicates(subset=["reviewId"])
    mentah = mentah[mentah["content"].notna() & (mentah["content"].str.strip() != "")]

    # ── Tabel ulasan (akumulatif) + tabel jembatan kategori ───────────────
    df = gabung_dengan_arsip(bangun_tabel_ulasan(mentah))
    total_n = len(df)
    print(f"Data bersih (akumulatif): {total_n} review")

    df.to_csv(REVIEWS_CSV, index=False, encoding="utf-8")  # UTF-8 polos tanpa BOM: aman untuk Google Sheets/Looker Studio
    jembatan = (
        df[["review_id", "kategori"]]
        .assign(kategori=lambda d: d["kategori"].str.split(", "))
        .explode("kategori")
    )
    jembatan.to_csv(KATEGORI_CSV, index=False, encoding="utf-8")
    tabel_kategori_lengkap(df).to_csv(KATEGORI_LENGKAP_CSV, index=False, encoding="utf-8")

    # ── Agregat untuk data.json (skema sama seperti sebelumnya) ───────────
    distribusi_bintang = (
        df["bintang"].value_counts().sort_index().reindex(range(1, 6), fill_value=0).to_dict()
    )
    distribusi_sentimen = df["sentimen"].value_counts().to_dict()

    tren_tahun = df.groupby(["tahun", "sentimen"]).size().unstack(fill_value=0).sort_index()
    tren_per_tahun = [
        {
            "tahun": int(tahun),
            "Positif": int(row.get("Positif", 0)),
            "Netral": int(row.get("Netral", 0)),
            "Negatif": int(row.get("Negatif", 0)),
        }
        for tahun, row in tren_tahun.iterrows()
        if not pd.isna(tahun)
    ]
    avg_bintang_per_tahun = (
        df.dropna(subset=["tahun"]).groupby("tahun")["bintang"].mean().round(2).to_dict()
    )
    avg_bintang_per_tahun = {int(k): v for k, v in avg_bintang_per_tahun.items()}

    freq_kategori = dict(Counter(jembatan["kategori"]).most_common())
    responsivitas = {
        "Ya": int(df["ada_balasan"].sum()),
        "Tidak": int((~df["ada_balasan"]).sum()),
    }

    sample = df.head(20)[["isi", "bintang", "tanggal", "likes", "versi"]].copy()
    sample["tanggal"] = sample["tanggal"].astype(str)
    sample = sample.where(pd.notnull(sample), None)
    sample_reviews = sample.rename(columns={"isi": "isi"}).to_dict(orient="records")

    output = {
        "last_updated": now_wita.isoformat(),
        "app_info": {
            "title": info.get("title"),
            "developer": info.get("developer"),
            "score": round(info.get("score", 0), 2),
            "ratings": info.get("ratings"),
            "version": info.get("version"),
            "installs": info.get("installs"),
        },
        "periode": {
            "mulai": df["tanggal"].min().strftime("%Y-%m-%d"),
            "selesai": df["tanggal"].max().strftime("%Y-%m-%d"),
        },
        "total_review": total_n,
        "rata_rata_bintang": round(df["bintang"].mean(), 2) if total_n else 0,
        "distribusi_bintang": distribusi_bintang,
        "distribusi_sentimen": distribusi_sentimen,
        "tren_per_tahun": tren_per_tahun,
        "avg_bintang_per_tahun": avg_bintang_per_tahun,
        "frekuensi_kategori": freq_kategori,
        "responsivitas_developer": responsivitas,
        "sample_reviews": sample_reviews,
    }
    output = sanitize_for_json(output)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, allow_nan=False)

    print(f"Selesai. Ditulis: {OUTPUT_PATH}, {REVIEWS_CSV}, {KATEGORI_CSV}, {KATEGORI_LENGKAP_CSV}")


if __name__ == "__main__":
    main()
