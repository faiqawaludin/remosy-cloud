SELECT
    article_id,
    'Google News' AS platform,
    published_at,
    published_date_wib,
    keyword,
    publisher,
    title,
    url,
    cleaned_text,
    scraped_at
FROM {{ ref('stg_news') }}

UNION ALL

SELECT
    article_id,
    platform,
    published_at,
    published_date_wib,
    keyword,
    publisher,
    title,
    url,
    cleaned_text,
    scraped_at
FROM {{ ref('stg_tweets') }}