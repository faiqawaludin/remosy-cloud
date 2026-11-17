{{ config(post_hook="ALTER TABLE {{ this }} ADD PRIMARY KEY (sentiment_key) NOT ENFORCED") }}
SELECT
    TO_HEX(MD5(sentiment_label)) AS sentiment_key,
    sentiment_label,
    sentiment_polarity
FROM UNNEST([
    STRUCT('Positif' AS sentiment_label, 1 AS sentiment_polarity),
    STRUCT('Netral' AS sentiment_label, 0 AS sentiment_polarity),
    STRUCT('Negatif' AS sentiment_label, -1 AS sentiment_polarity),
    STRUCT('Belum Diproses' AS sentiment_label, 0 AS sentiment_polarity)
])