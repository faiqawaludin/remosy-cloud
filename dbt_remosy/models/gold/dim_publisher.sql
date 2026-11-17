{{ config(post_hook="ALTER TABLE {{ this }} ADD PRIMARY KEY (publisher_key) NOT ENFORCED") }}
WITH unique_publishers AS (
    SELECT DISTINCT
        COALESCE(NULLIF(TRIM(publisher), ''), 'Unknown Publisher') AS publisher_name
    FROM {{ ref('stg_news') }}
)

SELECT
    TO_HEX(MD5(publisher_name)) AS publisher_key,
    publisher_name
FROM unique_publishers