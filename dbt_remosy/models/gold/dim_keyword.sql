{{ config(post_hook="ALTER TABLE {{ this }} ADD PRIMARY KEY (keyword_key) NOT ENFORCED") }}
WITH unique_keywords AS (
    SELECT DISTINCT
        COALESCE(NULLIF(TRIM(keyword), ''), 'Uncategorized') AS keyword_name
    FROM {{ ref('stg_news') }}
)

SELECT
    TO_HEX(MD5(keyword_name)) AS keyword_key,
    keyword_name
FROM unique_keywords