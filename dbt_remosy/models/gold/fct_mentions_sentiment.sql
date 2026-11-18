{{
    config(
        post_hook="ALTER TABLE {{ this }} ADD PRIMARY KEY (mention_id) NOT ENFORCED, ADD CONSTRAINT fk_mentions_date FOREIGN KEY (date_key) REFERENCES {{ ref('dim_date') }} (date_key) NOT ENFORCED, ADD CONSTRAINT fk_mentions_platform FOREIGN KEY (platform_key) REFERENCES {{ ref('dim_platform') }} (platform_key) NOT ENFORCED, ADD CONSTRAINT fk_mentions_publisher FOREIGN KEY (publisher_key) REFERENCES {{ ref('dim_publisher') }} (publisher_key) NOT ENFORCED, ADD CONSTRAINT fk_mentions_keyword FOREIGN KEY (keyword_key) REFERENCES {{ ref('dim_keyword') }} (keyword_key) NOT ENFORCED, ADD CONSTRAINT fk_mentions_sentiment FOREIGN KEY (sentiment_key) REFERENCES {{ ref('dim_sentiment') }} (sentiment_key) NOT ENFORCED"
    )
}}

WITH mentions AS (
    SELECT *
    FROM {{ ref('stg_mentions') }}
),

sentiment AS (
    SELECT *
    FROM {{ source('remosy_silver', 'mentions_sentiment') }}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY article_id
        ORDER BY predicted_at DESC
    ) = 1
)

SELECT
    m.mention_id,
    CAST(FORMAT_DATE('%Y%m%d', m.published_date_wib) AS INT64) AS date_key,
    TO_HEX(MD5(COALESCE(m.platform, 'Unknown'))) AS platform_key,
    TO_HEX(MD5(COALESCE(m.publisher, 'Unknown'))) AS publisher_key,
    TO_HEX(MD5(COALESCE(m.keyword, 'Unknown'))) AS keyword_key,
    TO_HEX(MD5(COALESCE(s.sentiment_label, 'Belum Diproses'))) AS sentiment_key,
    m.title,
    m.url,
    1 AS mention_count,
    m.likes_count,
    m.retweets_count,
    COALESCE(s.sentiment_score, 0.0) AS sentiment_score,
    CASE COALESCE(s.sentiment_label, 'Belum Diproses')
        WHEN 'Positif' THEN 1
        WHEN 'Negatif' THEN -1
        ELSE 0
    END AS sentiment_polarity,
    CASE WHEN s.is_hybrid_override THEN 1 ELSE 0 END AS is_hybrid_override_flag,
    m.published_at,
    m.scraped_at,
    s.predicted_at
FROM mentions m
LEFT JOIN sentiment s
    ON m.mention_id = s.article_id