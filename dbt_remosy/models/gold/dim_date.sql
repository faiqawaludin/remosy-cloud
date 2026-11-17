WITH date_bounds AS (
    SELECT
        COALESCE(MIN(DATE(published_at, 'Asia/Jakarta')), CURRENT_DATE('Asia/Jakarta')) AS min_date,
        COALESCE(MAX(DATE(published_at, 'Asia/Jakarta')), CURRENT_DATE('Asia/Jakarta')) AS max_date
    FROM {{ ref('stg_news') }}
),

date_spine AS (
    SELECT d
    FROM date_bounds,
    UNNEST(GENERATE_DATE_ARRAY(min_date, max_date)) AS d
)

SELECT
    CAST(FORMAT_DATE('%Y%m%d', d) AS INT64) AS date_key,
    d AS full_date,
    EXTRACT(YEAR FROM d) AS year,
    EXTRACT(MONTH FROM d) AS month,
    FORMAT_DATE('%B', d) AS month_name,
    EXTRACT(DAY FROM d) AS day,
    FORMAT_DATE('%A', d) AS day_name,
    EXTRACT(DAYOFWEEK FROM d) IN (1, 7) AS is_weekend
FROM date_spine