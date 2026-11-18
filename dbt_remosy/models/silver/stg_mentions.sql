SELECT
    article_id AS mention_id,
    'Google News' AS platform,
    published_at,
    DATE(published_at, 'Asia/Jakarta') AS published_date_wib,
    keyword,
    publisher,
    title,
    url,
    cleaned_text,
    0 AS likes_count,
    0 AS retweets_count,
    scraped_at
FROM {{ ref('stg_news') }}

UNION ALL

SELECT
    article_id AS mention_id,
    platform,
    published_at,
    DATE(published_at, 'Asia/Jakarta') AS published_date_wib,
    keyword,
    publisher,
    title,
    url,
    cleaned_text,
    COALESCE(likes_count, 0) AS likes_count,
    COALESCE(retweets_count, 0) AS retweets_count,
    scraped_at
FROM {{ ref('stg_tweets') }}