WITH base AS (
    SELECT
        m.published_date_wib,
        m.platform,
        m.keyword,
        COALESCE(s.sentiment_label, 'Belum Diproses') AS sentiment_label,
        LOWER(REGEXP_REPLACE(m.cleaned_text, r'[^a-zA-Z0-9\s]', ' ')) AS clean_body
    FROM {{ ref('stg_mentions') }} m
    LEFT JOIN {{ source('remosy_silver', 'mentions_sentiment') }} s
        ON m.mention_id = s.article_id
),

words AS (
    SELECT
        published_date_wib,
        platform,
        keyword,
        sentiment_label,
        word
    FROM base,
    UNNEST(SPLIT(clean_body, ' ')) AS word
    WHERE LENGTH(word) > 3
      AND word NOT IN (
          'yang', 'untuk', 'dengan', 'dalam', 'pada', 'dari', 'akan', 'oleh',
          'atau', 'juga', 'sudah', 'bisa', 'dapat', 'lebih', 'sebagai', 'tidak',
          'ini', 'itu', 'dan', 'ke', 'di', 'https', 'http', 'com'
      )
)

SELECT
    published_date_wib,
    platform,
    keyword,
    sentiment_label,
    word,
    COUNT(*) AS word_frequency
FROM words
GROUP BY 1, 2, 3, 4, 5