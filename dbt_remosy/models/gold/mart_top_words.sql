WITH news_with_sentiment AS (
    SELECT
        DATE(n.published_at, 'Asia/Jakarta') AS published_date_wib,
        n.keyword,
        COALESCE(s.sentiment_label, 'Belum Diproses') AS sentiment_label,
        n.cleaned_text
    FROM {{ ref('stg_news') }} n
    LEFT JOIN (
        SELECT article_id, sentiment_label
        FROM {{ source('remosy_silver', 'news_sentiment') }}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY article_id ORDER BY predicted_at DESC) = 1
    ) s ON n.article_id = s.article_id
),

words_exploded AS (
    SELECT
        published_date_wib,
        keyword,
        sentiment_label,
        word
    FROM news_with_sentiment,
    UNNEST(SPLIT(cleaned_text, ' ')) AS word
)

SELECT
    published_date_wib,
    keyword,
    sentiment_label,
    word,
    COUNT(*) AS word_frequency
FROM words_exploded
WHERE LENGTH(word) >= 4
  AND word NOT IN (
      'yang', 'dan', 'dari', 'ini', 'itu', 'untuk', 'pada', 'dengan', 'adalah',
      'dalam', 'tidak', 'akan', 'juga', 'atau', 'ada', 'oleh', 'bisa', 'saat',
      'sebagai', 'tahun', 'tersebut', 'lebih', 'sudah', 'karena', 'serta',
      'dapat', 'bagi', 'para', 'hingga', 'secara', 'antara', 'menjadi', 'bahwa',
      'atas', 'hal', 'namun', 'masih', 'jika', 'lain', 'bahkan', 'belum', 'lagi',
      'baru', 'banyak', 'setiap', 'harus', 'selama', 'telah', 'salah', 'satu',
      'dua', 'tiga', 'empat', 'lima', 'kami', 'kita', 'mereka', 'dia', 'ia',
      'anda', 'saya', 'nya', 'pun', 'per', 'tentang', 'seperti', 'melalui',
      'terhadap', 'menurut', 'kembali', 'tetapi', 'yakni', 'yaitu', 'baca',
      'berita', 'artikel', 'foto', 'jakarta', 'karawang', 'unsika', 'universitas',
      'singaperbangsa'
  )
GROUP BY
    published_date_wib,
    keyword,
    sentiment_label,
    word