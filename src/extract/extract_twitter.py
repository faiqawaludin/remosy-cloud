import base64
import html
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "remosy-cloud-dw")
TABLE_ID = f"{PROJECT_ID}.remosy_bronze.tweets_raw"


def _decode_bing_url(raw_link: str) -> str:
    """Mendekode URL asli dari redirect Bing (parameter u=a1<base64>)."""
    try:
        parsed = urllib.parse.urlparse(raw_link)
        qs = urllib.parse.parse_qs(parsed.query)
        if "u" in qs and qs["u"][0].startswith("a1"):
            encoded = qs["u"][0][2:]
            padded = encoded + "=" * (-len(encoded) % 4)
            return base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
        pass
    return raw_link


def _clean_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_bing_x_posts(query: str, label: str, max_items: int = 30) -> list[dict]:
    encoded_q = urllib.parse.quote(f'site:x.com "{query}"')
    rss_url = f"https://www.bing.com/search?q={encoded_q}&format=rss"
    rows = []
    now_utc = datetime.now(UTC)

    try:
        req = urllib.request.Request(
            rss_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        for item in root.findall(".//item")[:max_items]:
            raw_link = (item.findtext("link") or "").strip()
            real_url = _decode_bing_url(raw_link)
            title = _clean_html(item.findtext("title") or "")
            desc = _clean_html(item.findtext("description") or "")
            pub_date = (item.findtext("pubDate") or "").strip()

            match = re.search(
                r"https?://(?:x|twitter)\.com/([^/]+)/status/(\d+)", real_url
            )
            if not match:
                continue

            username = match.group(1)
            if username.lower() in {"search", "hashtag", "i", "home", "explore"}:
                continue

            full_text = desc if len(desc) > 15 else title
            if not full_text:
                continue

            rows.append(
                {
                    "scraped_at": now_utc,
                    "created_at": pub_date,
                    "keyword": label,
                    "username": username,
                    "full_text": full_text,
                    "tweet_url": f"https://x.com/{username}/status/{match.group(2)}",
                    "likes": 0,
                    "retweets": 0,
                }
            )
    except Exception as e:
        print(f"   [WARNING Bing X Index '{query}']: {e}", flush=True)

    return rows


def fetch_google_x_posts(query: str, label: str, max_items: int = 30) -> list[dict]:
    encoded_q = urllib.parse.quote(f'site:x.com "{query}"')
    rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=id&gl=ID&ceid=ID:id"
    rows = []
    now_utc = datetime.now(UTC)

    try:
        req = urllib.request.Request(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        for item in root.findall(".//item")[:max_items]:
            link = (item.findtext("link") or "").strip()
            title = _clean_html(item.findtext("title") or "")
            pub_date = (item.findtext("pubDate") or "").strip()

            # Format umum judul Google Index untuk X: "Teks cuitan - Nama (@handle) on X"
            handle_match = re.search(r"@([A-Za-z0-9_]{1,15})", title)
            username = handle_match.group(1) if handle_match else "x_public_user"
            clean_title = re.sub(r"\s*-\s*[^-]+on X$", "", title).strip()

            if not link or not clean_title:
                continue

            rows.append(
                {
                    "scraped_at": now_utc,
                    "created_at": pub_date,
                    "keyword": label,
                    "username": username,
                    "full_text": clean_title,
                    "tweet_url": link,
                    "likes": 0,
                    "retweets": 0,
                }
            )
    except Exception as e:
        print(f"   [WARNING Google X Index '{query}']: {e}", flush=True)

    return rows


def run_twitter_scraping_job():
    print("Memulai Job Scraping X/Twitter -> BigQuery Bronze...", flush=True)
    client = bigquery.Client(project=PROJECT_ID)

    try:
        query_existing = f"SELECT DISTINCT tweet_url FROM `{TABLE_ID}`"
        existing_links = set(
            client.query(query_existing).to_dataframe()["tweet_url"].tolist()
        )
        print(f"Ditemukan {len(existing_links)} tweet historis di Bronze.", flush=True)
    except Exception:
        existing_links = set()

    queries = [
        ("unsika", "UNSIKA"),
        ("universitas singaperbangsa karawang", "Universitas Singaperbangsa Karawang"),
    ]

    collected = []
    for q, label in queries:
        bing_rows = fetch_bing_x_posts(q, label)
        google_rows = fetch_google_x_posts(q, label)
        print(
            f"   -> '{label}': {len(bing_rows)} dari Bing Index, {len(google_rows)} dari Google Index.",
            flush=True,
        )
        collected.extend(bing_rows)
        collected.extend(google_rows)

    if not collected:
        print("Tidak ada tweet baru yang ditemukan saat ini.", flush=True)
        return

    df = pd.DataFrame(collected)
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], utc=True)
    df_new = df[~df["tweet_url"].isin(existing_links)].drop_duplicates(
        subset=["tweet_url"]
    )

    if not df_new.empty:
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
        job = client.load_table_from_dataframe(df_new, TABLE_ID, job_config=job_config)
        job.result()
        print(f"Berhasil memuat {len(df_new)} tweet BARU ke {TABLE_ID}!", flush=True)
    else:
        print("Semua tweet yang ditarik sudah tersimpan di Bronze.", flush=True)


if __name__ == "__main__":
    run_twitter_scraping_job()
