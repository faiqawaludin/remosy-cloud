{{
    config(
        post_hook=[
            "ALTER TABLE {{ this }} ADD PRIMARY KEY (article_id) NOT ENFORCED",
            "ALTER TABLE {{ this }} ADD CONSTRAINT fk_news_date FOREIGN KEY (date_key) REFERENCES {{ ref('dim_date') }} (date_key) NOT ENFORCED",
            "ALTER TABLE {{ this }} ADD CONSTRAINT fk_news_publisher FOREIGN KEY (publisher_key) REFERENCES {{ ref('dim_publisher') }} (publisher_key) NOT ENFORCED",
            "ALTER TABLE {{ this }} ADD CONSTRAINT fk_news_keyword FOREIGN KEY (keyword_key) REFERENCES {{ ref('dim_keyword') }} (keyword_key) NOT ENFORCED",
            "ALTER TABLE {{ this }} ADD CONSTRAINT fk_news_sentiment FOREIGN KEY (sentiment_key) REFERENCES {{ ref('dim_sentiment') }} (sentiment_key) NOT ENFORCED"
        ]
    )
}}
WITH news AS (
    SELECT *
    FROM {{ ref('stg_news') }}
),

sentiment AS (
    SELECT *
    FROM {{ source('remosy_silver', 'news_sentiment') }}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY article_id
        ORDER BY predicted_at DESC
    ) = 1
),

joined AS (
    SELECT
        n.article_id,
        DATE(n.published_at, 'Asia/Jakarta') AS published_date_wib,
        COALESCE(NULLIF(TRIM(n.publisher), ''), 'Unknown Publisher') AS publisher_name,
        COALESCE(NULLIF(TRIM(n.keyword), ''), 'Uncategorized') AS keyword_name,
        COALESCE(s.sentiment_label, 'Belum Diproses') AS sentiment_label,
        n.title,
        n.url,
        s.sentiment_score,
        COALESCE(s.is_hybrid_override, FALSE) AS is_hybrid_override,
        n.published_at,
        n.scraped_at,
        s.predicted_at
    FROM news n
    LEFT JOIN sentiment s
        ON n.article_id = s.article_id
)

SELECT
    j.article_id,
    CAST(FORMAT_DATE('%Y%m%d', j.published_date_wib) AS INT64) AS date_key,
    TO_HEX(MD5(j.publisher_name)) AS publisher_key,
    TO_HEX(MD5(j.keyword_name)) AS keyword_key,
    ds.sentiment_key,
    j.title,
    j.url,
    1 AS article_count,
    j.sentiment_score,
    ds.sentiment_polarity,
    CAST(j.is_hybrid_override AS INT64) AS is_hybrid_override_flag,
    j.published_at,
    j.scraped_at,
    j.predicted_at
FROM joined j
LEFT JOIN {{ ref('dim_sentiment') }} ds
    ON j.sentiment_label = ds.sentiment_label