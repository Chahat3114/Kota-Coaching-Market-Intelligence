-- Kota Coaching Market Intelligence Dashboard — SQL Analysis
-- Run against coaching_intel.db (SQLite)
-- Demonstrates: JOINs, CTEs, window functions, GROUP BY/HAVING

-- Query 1: Institutes ranked by sentiment, with sample-size reliability flagged
SELECT institute, avg_sentiment, comment_count, reliable
FROM sentiment_by_institute
ORDER BY avg_sentiment DESC;

-- Query 2: Top complaint theme per institute (CTE + window function)
WITH ranked AS (
  SELECT institute, themes, mention_count,
         RANK() OVER (PARTITION BY institute ORDER BY mention_count DESC) AS rnk
  FROM complaint_theme_distribution
)
SELECT institute, themes AS top_complaint, mention_count
FROM ranked
WHERE rnk = 1;

-- Query 3: Value-for-money score (sentiment per ₹1L of annual fee)
SELECT institute, annual_fee, avg_sentiment, value_score
FROM fee_vs_sentiment
WHERE reliable = 1
ORDER BY value_score DESC;

-- Query 4: JOIN — what % of mentions for each theme are actually negative
-- (distinguishes "people talk about this a lot" from "people complain about this a lot")
SELECT t.institute, t.themes,
       t.mention_count AS total_mentions,
       COALESCE(c.mention_count, 0) AS negative_mentions,
       ROUND(100.0 * COALESCE(c.mention_count, 0) / t.mention_count, 1) AS pct_negative
FROM theme_mention_volume t
LEFT JOIN complaint_theme_distribution c
  ON t.institute = c.institute AND t.themes = c.themes
WHERE t.themes != 'uncategorized'
ORDER BY pct_negative DESC;

-- Query 5: GROUP BY + HAVING — only institutes with a statistically reliable sample (400+ comments)
SELECT institute, comment_count, avg_sentiment
FROM sentiment_by_institute
GROUP BY institute
HAVING comment_count >= 400
ORDER BY avg_sentiment DESC;

-- Query 6: Window function — rank institutes by sentiment trend (improving vs. declining)
SELECT institute, pct_change,
       RANK() OVER (ORDER BY pct_change DESC) AS trend_rank
FROM trend_summary
ORDER BY trend_rank;
