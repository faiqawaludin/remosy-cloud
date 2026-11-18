import os
import subprocess
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "remosy-cloud-dw")
TABLE_ID = f"{PROJECT_ID}.remosy_bronze.tweets_raw"


class TwitterScraper:
    def __init__(self):
        self.auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()

    def get_since_date(self, days=7):
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    def scrape(self, query: str, max_items: int = 50) -> pd.DataFrame:
        if not self.auth_token:
            print(
                "[WARNING] TWITTER_AUTH_TOKEN belum diatur. Melewati scraping X/Twitter.",
                flush=True,
            )
            return pd.DataFrame()

        print(f"Mencari Tweet untuk kata kunci: '{query}'...", flush=True)
        since_date = self.get_since_date(days=7)
        search_query = f"{query} since:{since_date}"
        filename = "temp_tweets.csv"

        command = (
            f'npx -y tweet-harvest@2.6.1 -o "{filename}" '
            f'-s "{search_query}" '
            f'--tab "LATEST" '
            f"-l {max_items} "
            f"--token {self.auth_token}"
        )

        try:
            process = subprocess.run(
                command, shell=True, capture_output=True, text=True
            )
            output_log = (process.stdout + process.stderr).lower()

            if any(
                err in output_log
                for err in ["unauthorized", "invalid token", "rate limit"]
            ):
                print(
                    f"[WARNING] Auth Token X/Twitter kedaluwarsa atau terkena rate limit:\n{output_log[:300]}",
                    flush=True,
                )
                return pd.DataFrame()

            expected_file = os.path.join("tweets-data", filename)
            if not os.path.exists(expected_file):
                return pd.DataFrame()

            df = pd.read_csv(expected_file)
            os.remove(expected_file)

            if df.empty:
                return pd.DataFrame()

            clean_df = pd.DataFrame()
            clean_df["scraped_at"] = pd.to_datetime(
                [datetime.utcnow()] * len(df), utc=True
            )
            clean_df["created_at"] = df.get("created_at", "").astype(str)
            clean_df["keyword"] = query
            clean_df["username"] = (
                df.get("username", "unknown").fillna("unknown").astype(str)
            )
            clean_df["full_text"] = df.get("full_text", "").fillna("").astype(str)
            clean_df["tweet_url"] = df.get("tweet_url", "").fillna("").astype(str)
            clean_df["likes"] = (
                pd.to_numeric(df.get("favorite_count", 0), errors="coerce")
                .fillna(0)
                .astype(int)
            )
            clean_df["retweets"] = (
                pd.to_numeric(df.get("retweet_count", 0), errors="coerce")
                .fillna(0)
                .astype(int)
            )

            # Buang baris tanpa URL valid
            clean_df = clean_df[clean_df["tweet_url"] != ""]
            return clean_df

        except Exception as e:
            print(f"[WARNING] Error Tweet-Harvest pada '{query}': {e}", flush=True)
            return pd.DataFrame()


def run_twitter_scraping_job():
    print("Memulai Job Scraping X/Twitter -> BigQuery Bronze...", flush=True)
    keywords = [
        "Universitas Singaperbangsa Karawang",
        "UNSIKA",
        "Universitas Singaperbangsa",
        "Unsika",
        "Unsika Karawang",
    ]

    client = bigquery.Client(project=PROJECT_ID)
    scraper = TwitterScraper()

    # 1. Cek URL tweet yang sudah tersimpan di Bronze
    try:
        query_existing = f"SELECT DISTINCT tweet_url FROM `{TABLE_ID}`"
        existing_links = set(
            client.query(query_existing).to_dataframe()["tweet_url"].tolist()
        )
        print(f"Ditemukan {len(existing_links)} tweet historis di Bronze.", flush=True)
    except Exception:
        existing_links = set()

    all_new_dfs = []

    for kw in keywords:
        df = scraper.scrape(kw, max_items=50)
        print(f"   -> Menarik {len(df)} tweet mentah untuk '{kw}'.", flush=True)

        if not df.empty:
            df_new = df[~df["tweet_url"].isin(existing_links)].drop_duplicates(
                subset=["tweet_url"]
            )
            if not df_new.empty:
                existing_links.update(df_new["tweet_url"].tolist())
                all_new_dfs.append(df_new)

    # 2. Load ke BigQuery Bronze (WRITE_APPEND)
    if all_new_dfs:
        final_df = pd.concat(all_new_dfs, ignore_index=True)
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
        job = client.load_table_from_dataframe(
            final_df, TABLE_ID, job_config=job_config
        )
        job.result()
        print(f"Berhasil memuat {len(final_df)} tweet BARU ke {TABLE_ID}!", flush=True)
    else:
        print("Tidak ada tweet baru yang perlu dimuat ke Bronze.", flush=True)


if __name__ == "__main__":
    run_twitter_scraping_job()
