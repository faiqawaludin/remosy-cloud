{{
    config(
        materialized='table',
        partition_by={
            "field": "scraped_at",
            "data_type": "timestamp",
            "granularity": "day"
        },
        cluster_by=['keyword']
    )
}}

WITH raw_source AS (
    SELECT
        article_id,
        keyword,
        title,
        url,
        published_date,
        publisher,
        raw_text,
        scraped_at
    FROM {{ source('remosy_bronze', 'news_raw') }}
),

deduplicated AS (
    SELECT *
    FROM raw_source
    -- Ambil 1 versi terbaru jika ada article_id ganda
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY article_id
        ORDER BY scraped_at DESC
    ) = 1
),

cleaned AS (
    SELECT
        article_id,
        keyword,
        TRIM(title) AS title,
        url,
        publisher,
        SAFE.PARSE_TIMESTAMP('%a, %d %b %Y %H:%M:%S %Z', published_date) AS published_at,
        TRIM(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    LOWER(
                        REGEXP_REPLACE(
                            CONCAT(COALESCE(title, ''), '. ', COALESCE(raw_text, '')),
                            r'https?://\S+|www\.\S+',
                            ' '
                        )
                    ),
                    r'[^a-z\s]',
                    ' '
                ),
                r'\s+',
                ' '
            )
        ) AS cleaned_text,
        scraped_at
    FROM deduplicated
)

SELECT
    article_id,
    keyword,
    title,
    url,
    publisher,
    COALESCE(published_at, scraped_at) AS published_at,
    cleaned_text,
    scraped_at
FROM cleaned
WHERE LENGTH(cleaned_text) > 20
  AND REGEXP_CONTAINS(cleaned_text, r'\b(unsika|singaperbangsa)\b')