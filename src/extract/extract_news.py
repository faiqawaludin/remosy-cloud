import hashlib
import os
from datetime import UTC, datetime

import pandas as pd
import trafilatura
from dotenv import load_dotenv
from gnews import GNews
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BQ_LOCATION = os.getenv("BQ_LOCATION", "US")
DATASET_ID = "remosy_bronze"
TABLE_ID = "news_raw"


def ensure_bronze_dataset(client: bigquery.Client):
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = BQ_LOCATION
    client.create_dataset(dataset, exists_ok=True)


def get_existing_article_ids(client: bigquery.Client) -> set[str]:
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    query = f"""
        SELECT DISTINCT article_id
        FROM `{table_ref}`
        WHERE scraped_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
    """
    try:
        results = client.query(query).result()
        return {row.article_id for row in results}
    except NotFound:
        return set()


def scrape_google_news(
    keywords: list[str], existing_ids: set[str], max_results: int = 10
) -> pd.DataFrame:
    google_news = GNews(
        language="id", country="ID", period="7d", max_results=max_results
    )
    records = []
    seen_in_this_run = set()
    scraped_time = datetime.now(UTC)

    for kw in keywords:
        print(f"Mencari berita untuk kata kunci: '{kw}'...")
        articles = google_news.get_news(kw)

        for art in articles:
            url = art.get("url", "")
            article_id = hashlib.md5(url.encode("utf-8")).hexdigest()

            if article_id in existing_ids or article_id in seen_in_this_run:
                continue

            seen_in_this_run.add(article_id)

            downloaded = trafilatura.fetch_url(url)
            raw_text = trafilatura.extract(downloaded) if downloaded else ""

            records.append(
                {
                    "article_id": article_id,
                    "keyword": kw,
                    "title": art.get("title", ""),
                    "url": url,
                    "published_date": art.get("published date", ""),
                    "publisher": art.get("publisher", {}).get("title", ""),
                    "raw_text": raw_text or "",
                    "scraped_at": scraped_time,
                }
            )

    return pd.DataFrame(records)


def load_to_bigquery(client: bigquery.Client, df: pd.DataFrame):
    if df.empty:
        print("Tidak ada artikel baru yang perlu diunggah.")
        return

    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="scraped_at",
        ),
        clustering_fields=["keyword", "article_id"],
        autodetect=True,
    )

    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    print(f"Berhasil memuat {len(df)} artikel BARU ke {table_ref}!")


if __name__ == "__main__":
    bq_client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)
    ensure_bronze_dataset(bq_client)

    existing_ids = get_existing_article_ids(bq_client)
    print(f"Ditemukan {len(existing_ids)} artikel historis di Bronze.")

    target_keywords = [
        "Universitas Singaperbangsa Karawang",
        "UNSIKA",
        "Universitas Singaperbangsa",
        "Unsika",
        "Unsika Karawang",
    ]
    df_raw = scrape_google_news(target_keywords, existing_ids, max_results=10)
    load_to_bigquery(bq_client, df_raw)
