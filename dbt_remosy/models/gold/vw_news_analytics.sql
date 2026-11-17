{{ config(materialized='view') }}

SELECT
    f.article_id,
    d.full_date AS published_date,
    d.year,
    d.month_name,
    d.day_name,
    d.is_weekend,
    p.publisher_name,
    k.keyword_name,
    s.sentiment_label,
    s.sentiment_polarity,
    f.title,
    f.url,
    f.article_count,
    f.sentiment_score,
    f.is_hybrid_override_flag
FROM {{ ref('fct_news_sentiment') }} f
LEFT JOIN {{ ref('dim_date') }} d ON f.date_key = d.date_key
LEFT JOIN {{ ref('dim_publisher') }} p ON f.publisher_key = p.publisher_key
LEFT JOIN {{ ref('dim_keyword') }} k ON f.keyword_key = k.keyword_key
LEFT JOIN {{ ref('dim_sentiment') }} s ON f.sentiment_key = s.sentiment_key