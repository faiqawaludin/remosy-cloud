{{ config(post_hook="ALTER TABLE {{ this }} ADD PRIMARY KEY (platform_key) NOT ENFORCED") }}

WITH platforms AS (
    SELECT DISTINCT platform AS platform_name
    FROM {{ ref('stg_mentions') }}
    WHERE platform IS NOT NULL
)

SELECT
    TO_HEX(MD5(platform_name)) AS platform_key,
    platform_name
FROM platforms