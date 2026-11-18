import os
import re
from datetime import UTC, datetime

import pandas as pd
from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from transformers import pipeline

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BQ_LOCATION = os.getenv("BQ_LOCATION", "US")
SILVER_DATASET = "remosy_silver"
STG_TABLE = "stg_mentions"
SENTIMENT_TABLE = "news_sentiment"

# Kata kunci krisis reputasi institusi untuk Rule-Based Hybrid Override
CRISIS_KEYWORDS = [
    r"\bkorupsi\b",
    r"\bdemo\b",
    r"\bdemonstrasi\b",
    r"\bpenyimpangan\b",
    r"\bkekerasan seksual\b",
    r"\bpelecehan\b",
    r"\bpungli\b",
    r"\bskandal\b",
    r"\bterdakwa\b",
    r"\bpenjara\b",
    r"\bboikot\b",
    r"\bmogok\b",
    r"\bkecewa\b",
]


def get_unprocessed_news(client: bigquery.Client) -> pd.DataFrame:
    """Mengambil data bersih dari stg_news yang belum memiliki label sentimen."""
    stg_ref = f"{PROJECT_ID}.{SILVER_DATASET}.{STG_TABLE}"
    sent_ref = f"{PROJECT_ID}.{SILVER_DATASET}.{SENTIMENT_TABLE}"

    try:
        client.get_table(sent_ref)
        query = f"""
            SELECT s.article_id, s.cleaned_text
            FROM `{stg_ref}` s
            LEFT JOIN `{sent_ref}` n ON s.article_id = n.article_id
            WHERE n.article_id IS NULL
        """
    except NotFound:
        # Jika tabel news_sentiment belum ada (run pertama), ambil semua dari stg_news
        query = f"""
            SELECT article_id, cleaned_text
            FROM `{stg_ref}`
        """

    return client.query(query).to_dataframe()


def apply_hybrid_logic(
    text: str, raw_label: str, raw_score: float
) -> tuple[str, float, bool]:
    """Menstandarkan label IndoBERT dan menerapkan override untuk isu krisis."""
    mapping = {
        "positive": "Positif",
        "negative": "Negatif",
        "neutral": "Netral",
    }
    label = mapping.get(raw_label.lower(), "Netral")
    score = float(raw_score)
    is_overridden = False

    # Override ke Negatif jika mengandung kata kunci krisis institusi
    if label != "Negatif":
        for pattern in CRISIS_KEYWORDS:
            if re.search(pattern, text):
                label = "Negatif"
                score = max(score, 0.85)
                is_overridden = True
                break

    return label, score, is_overridden


def run_sentiment_inference(df: pd.DataFrame) -> pd.DataFrame:
    """Menjalankan model IndoBERT pada DataFrame berita baru."""
    print(
        "Memuat model IndoBERT (w11wo/indonesian-roberta-base-sentiment-classifier)..."
    )
    sentiment_pipe = pipeline(
        "sentiment-analysis",
        model="w11wo/indonesian-roberta-base-sentiment-classifier",
        truncation=True,
        max_length=512,
    )

    results = []
    predicted_time = datetime.now(UTC)

    for _, row in df.iterrows():
        text = str(row["cleaned_text"])
        pred = sentiment_pipe(text)[0]
        final_label, final_score, is_overridden = apply_hybrid_logic(
            text, pred["label"], pred["score"]
        )

        results.append(
            {
                "article_id": row["article_id"],
                "sentiment_label": final_label,
                "sentiment_score": round(final_score, 4),
                "is_hybrid_override": is_overridden,
                "predicted_at": predicted_time,
            }
        )

    return pd.DataFrame(results)


def load_sentiment_to_bigquery(client: bigquery.Client, df: pd.DataFrame):
    """Menyimpan hasil prediksi sentimen ke tabel remosy_silver.news_sentiment."""
    if df.empty:
        print("Tidak ada data baru untuk diprediksi.")
        return

    table_ref = f"{PROJECT_ID}.{SILVER_DATASET}.{SENTIMENT_TABLE}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        clustering_fields=["sentiment_label", "article_id"],
        autodetect=True,
    )

    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    print(f"Berhasil menyimpan {len(df)} hasil analisis sentimen ke {table_ref}!")


if __name__ == "__main__":
    bq_client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)
    df_unprocessed = get_unprocessed_news(bq_client)

    print(f"Ditemukan {len(df_unprocessed)} artikel baru yang belum dilabeli sentimen.")
    if not df_unprocessed.empty:
        df_predictions = run_sentiment_inference(df_unprocessed)
        load_sentiment_to_bigquery(bq_client, df_predictions)
