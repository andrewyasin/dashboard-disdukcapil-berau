"""
Script scraping review aplikasi Disdukcapil Berau dari Google Play Store.
Dijalankan otomatis setiap hari oleh GitHub Actions.
Output: docs/data.json (dibaca oleh dashboard di GitHub Pages)
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta

import pandas as pd
from google_play_scraper import Sort, app, reviews

# ── KONFIGURASI ──────────────────────────────────────────────────────────────
APP_ID = "com.disdukcapil.berau"  # Ganti jika app_id berbeda
OUTPUT_PATH = "docs/data.json"
MAX_REVIEWS = 1000
WITA = timezone(timedelta(hours=8))  # UTC+8

# ── KAMUS KATEGORI ───────────────────────────────────────────────────────────
KATEGORI_KEYWORDS = {
    "KTP / e-KTP": ["ktp", "e-ktp", "ktp digital", "kartu tanda penduduk", "nik"],
    "Akta Kelahiran": ["akta", "kelahiran", "lahir", "bayi", "anak"],
    "Kartu Keluarga": ["kk", "kartu keluarga", "anggota", "rumah tangga"],
    "Kecepatan Proses": [
        "lama", "lambat", "cepat", "lelet", "tunggu", "antri",
        "proses", "menunggu", "nunggu", "instan", "segera", "kilat",
    ],
    "Kemudahan Aplikasi": [
        "mudah", "susah", "ribet", "bingung", "sulit", "gampang",
        "simpel", "fitur", "menu", "tampilan", "navigasi", "ux",
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
    "Login / Akun": ["login", "akun", "masuk", "daftar", "registrasi", "kata sandi", "password"],
    "Update / Versi": ["update", "versi", "perbarui", "pembaharuan"],
}


def label_sentimen(score: int) -> str:
    if score >= 4:
        return "Positif"
    if score == 3:
        return "Netral"
    return "Negatif"


def kategorisasi(teks: str) -> str:
    if not isinstance(teks, str) or not teks.strip():
        return "Lainnya"
    teks_lower = teks.lower()
    hasil = [kat for kat, kws in KATEGORI_KEYWORDS.items() if any(kw in teks_lower for kw in kws)]
    return ", ".join(hasil) if hasil else "Lainnya"


def sanitize_for_json(obj):
    """Ganti semua NaN/NaT/Inf menjadi None secara rekursif agar selalu valid JSON."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float) and (pd.isna(obj) or obj in (float("inf"), float("-inf"))):
        return None
    if pd.isna(obj) if not isinstance(obj, (list, dict)) else False:
        return None
    return obj


def main() -> None:
    now_wita = datetime.now(WITA)
    print(f"[{now_wita.strftime('%Y-%m-%d %H:%M WITA')}] Mulai scraping aplikasi: {APP_ID}")

    # ── Info aplikasi ─────────────────────────────────────────────────────
    info = app(APP_ID, lang="id", country="id")

    # ── Scraping review ───────────────────────────────────────────────────
    result, _ = reviews(
        APP_ID,
        lang="id",
        country="id",
        sort=Sort.NEWEST,
        count=MAX_REVIEWS,
        filter_score_with=None,
    )
    df = pd.DataFrame(result)
    print(f"Berhasil mengambil {len(df)} review mentah")

    # ── Cleaning ──────────────────────────────────────────────────────────
    df = df.drop_duplicates(subset=["reviewId"])
    df = df[df["content"].notna() & (df["content"].str.strip() != "")]
    df["Sentimen"] = df["score"].apply(label_sentimen)
    df["Kategori"] = df["content"].apply(kategorisasi)
    df["AdaBalasan"] = df["replyContent"].notna()
    df["tanggal_dt"] = pd.to_datetime(df["at"], errors="coerce")
    df["tahun"] = df["tanggal_dt"].dt.year

    total_n = len(df)
    print(f"Data bersih: {total_n} review")

    # ── Statistik agregat ─────────────────────────────────────────────────
    distribusi_bintang = (
        df["score"].value_counts().sort_index().reindex(range(1, 6), fill_value=0).to_dict()
    )
    distribusi_sentimen = df["Sentimen"].value_counts().to_dict()

    tren_tahun = (
        df.groupby(["tahun", "Sentimen"]).size().unstack(fill_value=0).sort_index()
    )
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
        df.dropna(subset=["tahun"]).groupby("tahun")["score"].mean().round(2).to_dict()
    )
    avg_bintang_per_tahun = {int(k): v for k, v in avg_bintang_per_tahun.items()}

    semua_kategori = [c.strip() for cats in df["Kategori"] for c in cats.split(", ")]
    freq_kategori = dict(Counter(semua_kategori).most_common())

    balasan_counts = df["AdaBalasan"].value_counts()
    responsivitas = {
        "Ya": int(balasan_counts.get(True, 0)),
        "Tidak": int(balasan_counts.get(False, 0)),
    }

    tanggal_min = df["tanggal_dt"].min()
    tanggal_max = df["tanggal_dt"].max()

    # ── Sample review terbaru (untuk tabel di dashboard) ─────────────────
    sample_cols = ["userName", "content", "score", "at", "thumbsUpCount", "reviewCreatedVersion"]
    df_sample = df.sort_values("at", ascending=False)[sample_cols].head(20).copy()
    df_sample["at"] = df_sample["at"].astype(str)
    # Ganti semua NaN/NaT dengan None agar valid sebagai JSON (NaN bukan JSON yang sah)
    df_sample = df_sample.where(pd.notnull(df_sample), None)
    sample_reviews = df_sample.rename(
        columns={
            "userName": "nama",
            "content": "isi",
            "score": "bintang",
            "at": "tanggal",
            "thumbsUpCount": "likes",
            "reviewCreatedVersion": "versi",
        }
    ).to_dict(orient="records")

    # ── Susun JSON output ─────────────────────────────────────────────────
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
            "mulai": tanggal_min.strftime("%Y-%m-%d") if pd.notna(tanggal_min) else None,
            "selesai": tanggal_max.strftime("%Y-%m-%d") if pd.notna(tanggal_max) else None,
        },
        "total_review": total_n,
        "rata_rata_bintang": round(df["score"].mean(), 2) if total_n else 0,
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

    print(f"[{now_wita.strftime('%Y-%m-%d %H:%M WITA')}] Data berhasil disimpan ke {OUTPUT_PATH}")


if __name__ == "__main__":
    main()