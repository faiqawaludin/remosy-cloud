WITH raw_tweets AS (
    SELECT
        TO_HEX(MD5(tweet_url)) AS article_id,
        'X (Twitter)' AS platform,
        COALESCE(
            SAFE.PARSE_TIMESTAMP('%a %b %d %H:%M:%S %z %Y', created_at),
            scraped_at
        ) AS published_at,
        DATE(
            COALESCE(
                SAFE.PARSE_TIMESTAMP('%a %b %d %H:%M:%S %z %Y', created_at),
                scraped_at
            ),
            'Asia/Jakarta'
        ) AS published_date_wib,
        keyword,
        CONCAT('@', username) AS publisher,
        LEFT(REGEXP_REPLACE(full_text, r'\s+', ' '), 120) AS title,
        tweet_url AS url,
        TRIM(REGEXP_REPLACE(
            REGEXP_REPLACE(full_text, r'https?://\S+|@\w+|#\w+', ''),
            r'\s+', ' '
        )) AS cleaned_text,
        scraped_at,
        ROW_NUMBER() OVER (PARTITION BY tweet_url ORDER BY scraped_at DESC) AS rn
    FROM {{ source('remosy_bronze', 'tweets_raw') }}
    WHERE tweet_url IS NOT NULL AND full_text != ''
)

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
FROM raw_tweets
WHERE rn = 1