# REMOSY Cloud — Multi-Source Reputation Monitoring ELT Pipeline

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![Google BigQuery](https://img.shields.io/badge/Google_BigQuery-Data_Warehouse-4285F4?style=flat&logo=googlebigquery&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-1.12-FF694B?style=flat&logo=dbt&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-IndoBERT-FFD21E?style=flat&logo=huggingface&logoColor=black)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI%2FCD_WIF-2088FF?style=flat&logo=githubactions&logoColor=white)
![Looker Studio](https://img.shields.io/badge/Looker_Studio-BI_Dashboard-4285F4?style=flat&logo=googleanalytics&logoColor=white)

**REMOSY Cloud** (*Reputation Monitoring System*) adalah *end-to-end automated ELT & NLP pipeline* berbasis *cloud* untuk memantau persepsi dan sentimen publik terhadap **Universitas Singaperbangsa Karawang (UNSIKA)** dari dua kanal utama: **Google News** (media massa daring) dan **X / Twitter** (percakapan publik).

Sistem ini dirancang dengan standar rekayasa data modern menggunakan **Medallion Architecture** di Google BigQuery, pemodelan **Star Schema** dengan **dbt**, klasifikasi sentimen **IndoBERT + Rule-Based Hybrid Logic**, serta otomasi harian nir-kunci (*keyless authentication*) melalui **GitHub Actions**.

---

## Arsitektur Sistem

<img width="16384" height="4460" alt="System Architecture drawio" src="https://github.com/user-attachments/assets/b206f1a8-3233-461a-a76b-eb2cb639dfe1" />

## Fitur Utama & Keputusan Teknis

### 1. Medallion Architecture di Level Dataset
Pemisahan lapisan dilakukan di tingkat **BigQuery Dataset** untuk mengisolasi tata kelola akses (IAM), siklus retensi data, serta kejelasan *data lineage*:
* **`remosy_bronze`**: Menyimpan log data mentah hasil ekstraksi harian (`news_raw` dan `tweets_raw`) dengan mekanisme deduplikasi berbasis URL sebelum pemuatan (`WRITE_APPEND`).
* **`remosy_silver`**: Melakukan standardisasi zona waktu ke **WIB (`Asia/Jakarta`)**, pembersihan teks (*regex* URL, *mention*, *hashtag*, dan *whitespace*), serta penyatuan skema multi-sumber ke dalam model `stg_mentions`.
* **`remosy_gold`**: Menyajikan data siap konsumsi analitik dalam bentuk **Star Schema**, agregasi frekuensi kata (`mart_top_words`), dan *view* terdenormalisasi (`vw_reputation_analytics`).

### 2. Pemodelan Star Schema & Data Quality Testing (`dbt`)
Lapisan Gold menerapkan **Star Schema** dengan satu tabel fakta terpadu (`fct_mentions_sentiment`, *grain*: 1 baris per *mention* publik) yang terhubung ke lima tabel dimensi (`dim_date`, `dim_platform`, `dim_publisher`, `dim_keyword`, `dim_sentiment`).
* **Referential Integrity Metadata**: Menggunakan `post_hook` di dbt untuk mendaftarkan constraint `PRIMARY KEY` dan `FOREIGN KEY` (`NOT ENFORCED`) di BigQuery sehingga relasi antar-tabel terbaca langsung pada ERD tool seperti DBeaver.
* **Automated Data Quality Gates**: Menjalankan **22 pengujian otomatis** (`not_null`, `unique`, dan `relationships`) setiap kali pipeline selesai berjalan.

### 3. Hybrid NLP Sentiment Analysis (IndoBERT + Crisis Override)
* Menggunakan model *pretrained* **`w11wo/indonesian-roberta-base-sentiment-classifier`** untuk mengklasifikasikan setiap judul berita dan cuitan ke dalam kelas **Positif**, **Netral**, atau **Negatif** beserta *confidence score*-nya.
* Dilengkapi **Rule-Based Hybrid Override** (`is_hybrid_override`) berbasis *regex case-insensitive* untuk mendeteksi kata kunci krisis reputasi institusi (seperti *korupsi, demonstrasi, pungli, pelecehan, skandal*) agar isu berisiko tinggi tidak lolos sebagai sentimen netral akibat gaya bahasa jurnalistik yang formal.

### 4. CI/CD & Keamanan Keyless (Workload Identity Federation)
* Orkestrasi dijalankan secara terpusat oleh `run_pipeline.py` dan dijadwalkan otomatis setiap hari pukul **08:15 WIB (`01:15 UTC`)** melalui **GitHub Actions**.
* Autentikasi ke Google Cloud menggunakan **Workload Identity Federation (WIF)** tanpa menyimpan file JSON *Service Account Key* statis di repositori, serta memanfaatkan `actions/cache` untuk mempercepat pemuatan bobot model HuggingFace.

---

## Struktur Repositori

```text
remosy-cloud/
├── .github/
│   └── workflows/
│       └── daily_elt.yml             # Jadwal otomatis & CI/CD GitHub Actions (WIF)
├── dbt_remosy/
│   ├── models/
│   │   ├── bronze/
│   │   │   └── sources.yml           # Deklarasi sumber tabel Bronze
│   │   ├── silver/
│   │   │   ├── stg_news.sql          # Pembersihan & deduplikasi Google News
│   │   │   ├── stg_tweets.sql        # Pembersihan & deduplikasi X/Twitter
│   │   │   └── stg_mentions.sql      # Unifikasi multi-sumber (News + X)
│   │   └── gold/
│   │       ├── dim_date.sql          # Dimensi kalender (WIB)
│   │       ├── dim_platform.sql      # Dimensi kanal (Google News / X)
│   │       ├── dim_publisher.sql     # Dimensi media penerbit & akun X
│   │       ├── dim_keyword.sql       # Dimensi kata kunci pemantauan
│   │       ├── dim_sentiment.sql     # Dimensi kategori sentimen
│   │       ├── fct_mentions_sentiment.sql # Tabel fakta utama + PK/FK hooks
│   │       ├── mart_top_words.sql    # Data mart frekuensi kata populer
│   │       ├── vw_reputation_analytics.sql # View siap konsumsi Looker Studio
│   │       └── schema.yml            # 22 pengujian kualitas data dbt
│   └── dbt_project.yml
├── src/
│   ├── extract/
│   │   ├── extract_news.py           # Ekstraktor Google News RSS -> Bronze
│   │   └── extract_twitter.py        # Ekstraktor indeks publik X -> Bronze
│   └── ml/
│       └── predict_sentiment.py      # Inferensi IndoBERT + Hybrid Logic
├── run_pipeline.py                   # Orkestrator utama end-to-end ELT
├── requirements.txt                  # Daftar dependensi Python
└── README.md
```

---

## Cara Menjalankan Secara Lokal

### 1. Prasyarat
* Python 3.11+
* Google Cloud Project dengan BigQuery API aktif serta dataset `remosy_bronze`, `remosy_silver`, dan `remosy_gold`
* Google Cloud CLI (`gcloud`) terinstal untuk autentikasi lokal

### 2. Instalasi & Konfigurasi
```bash
# Clone repositori
git clone [https://github.com/faiqawaludin/remosy-cloud.git](https://github.com/faiqawaludin/remosy-cloud.git)
cd remosy-cloud

# Buat dan aktifkan virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Instal PyTorch CPU dan seluruh dependensi
pip install torch --index-url [https://download.pytorch.org/whl/cpu](https://download.pytorch.org/whl/cpu)
pip install -r requirements.txt
```

Buat file `.env` pada folder akar proyek:
```env
GCP_PROJECT_ID=remosy-cloud-dw
BQ_LOCATION=US
```

Lakukan autentikasi lokal ke Google Cloud:
```bash
gcloud auth application-default login
```

### 3. Eksekusi Pipeline Lengkap
```bash
python run_pipeline.py
```

---

## Pratinjau Data Warehouse & Dashboard

### Star Schema Diagram (`remosy_gold` — DBeaver)
> <img width="974" height="1016" alt="BigQuery@remosy-cloud-dw - remosy-cloud-dw - remosy_gold" src="https://github.com/user-attachments/assets/84b4d83c-4975-40f2-bc60-ba4b93aaaeb8" />

### Looker Studio Reputation Dashboard
> *Tambahkan tautan dan tangkapan layar dashboard Looker Studio di sini (`docs/dashboard_preview.png`).*

---

## Pengembang

**Muhamad Fa'iq Awaludin Syiam**  
*Data Engineer & Information Systems Graduate — Universitas Singaperbangsa Karawang*  
[GitHub](https://github.com/faiqawaludin)
