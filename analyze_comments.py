"""
Kota Coaching Market Intelligence Dashboard — Comment Analysis Pipeline (v2)
--------------------------------------------------------------------------------
Takes the raw YouTube comments CSV and produces the dashboard metric tables,
loads everything into SQLite, and runs example SQL queries on top.

Install once: pip install pandas vaderSentiment

institute_reference.csv format (you create this manually, ~10 rows):
    institute,annual_fee,locality,exam_focus
    Allen,150000,Indra Vihar,JEE+NEET
"""

import re
import sqlite3
import pandas as pd
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

INPUT_COMMENTS = "kota_coaching_comments_clean.csv"  # output of clean_raw_comments.py
INPUT_INSTITUTE_REF = "institute_reference.csv"
DB_PATH = "coaching_intel.db"
MIN_COMMENTS_FOR_RANKING = 20   # institutes below this are flagged, not dropped

analyzer = SentimentIntensityAnalyzer()

# ---------- Hinglish lexicon, fed directly into VADER ----------
# VADER scores words from -4 (very negative) to +4 (very positive).
# This is a living list — expand it once you've read real comments.
HINGLISH_LEXICON = {
    "acha": 2.0, "accha": 2.0, "achha": 2.0, "badiya": 2.2, "mast": 2.0,
    "zabardast": 2.8, "sahi": 1.5, "solid": 1.8,
    "bekar": -2.5, "bekaar": -2.5, "faltu": -2.3, "ganda": -2.0,
    "bakwas": -2.6, "bewakar": -2.0, "loot": -2.0, "dhokha": -2.5,
    "mehenga": -1.2, "overrated": -1.5, "khrab": -2.0,
}
analyzer.lexicon.update(HINGLISH_LEXICON)

# ---------- Phrase-level overrides ----------
# VADER scores word-by-word, so it misreads common Indian-internet praise
# idioms as negative (e.g. "hated by many defeated by none" uses negative
# words to mean "so good it draws envy"). Caught by manual review of real
# comments — documented here rather than silently mis-scored. This list
# will never be exhaustive; it's a known limitation of lexicon-based
# sentiment analysis, not a solved problem.
PRAISE_IDIOM_OVERRIDES = [
    "hated by many defeated by none", "no one can beat", "kr diya", "kar diya kill",
    "unmatched legacy", "kill kr diya", "killed it",
]


def apply_idiom_override(raw_text, base_score):
    t = str(raw_text).lower()
    if any(p in t for p in PRAISE_IDIOM_OVERRIDES):
        return max(base_score, 0.5)  # treat as at least mildly positive
    return base_score

# ---------- Theme keyword dictionary (English + common Hinglish) ----------
THEME_KEYWORDS = {
    "faculty_quality": ["faculty", "teacher", "teaching", "professor", "mentor",
                         "doubt session", "explain", "concept clarity", "ache teacher"],
    "batch_size": ["batch size", "overcrowd", "crowded", "too many students",
                    "class strength", "seater batch", "bada batch", "zyada bachhe"],
    "batch_placement": ["lower batch", "batch me dalte", "demote", "batch downgrade",
                         "achiever batch", "alpha batch", "beta batch"],
    "fees": ["fee", "fees", "expensive", "costly", "afford", "refund",
             "scholarship", "discount", "overpriced", "value for money",
             "mehenga", "paisa waste", "loot", "paisa kheech"],
    "hostel_mess": ["hostel", "mess food", "pg", "accommodation", "room"],
    "academic_pressure": ["pressure", "stress", "burnout", "competition",
                           "rank race", "anxiety", "mental health", "tension", "dabaav"],
    "infrastructure": ["infrastructure", "library", "lab facility", "classroom",
                        "campus", "building"],
    "marketing_credibility": ["fake result", "marketing gimmick", "inflated rank",
                               "selection claim", "advertisement", "scam", "lottery"],
}

PARENT_CUES = ["my son", "my daughter", "my child", "as a parent", "we sent him",
               "we sent her", "my kid", "as a mother", "as a father", "mera beta", "meri beti"]
STUDENT_CUES = ["my batch", "i am preparing", "i study here", "our faculty",
                "i joined", "i am a student", "dropper batch", "i am a repeater",
                "my classmates", "mera batch"]


def has_devanagari(text):
    """True if the comment contains Hindi script — VADER can't score this."""
    return any('\u0900' <= ch <= '\u097F' for ch in str(text))


def clean_text(text):
    text = str(text)
    text = re.sub(r"http\S+|www\.\S+", "", text)
    text = re.sub(r"[^a-zA-Z0-9\s']", " ", text)
    return text.lower().strip()


def score_sentiment(raw_text):
    """Returns NaN for pure Devanagari-script comments instead of a fake score."""
    if has_devanagari(raw_text):
        return np.nan
    base = analyzer.polarity_scores(clean_text(raw_text))["compound"]
    return apply_idiom_override(raw_text, base)


def tag_themes(raw_text):
    text_l = str(raw_text).lower()
    tags = [t for t, kws in THEME_KEYWORDS.items() if any(k in text_l for k in kws)]
    return tags if tags else ["uncategorized"]


def classify_role(raw_text):
    text_l = str(raw_text).lower()
    is_parent = any(c in text_l for c in PARENT_CUES)
    is_student = any(c in text_l for c in STUDENT_CUES)
    if is_parent and not is_student:
        return "parent"
    if is_student and not is_parent:
        return "student"
    if is_parent and is_student:
        return "ambiguous"
    return "unknown"


def process():
    df = pd.read_csv(INPUT_COMMENTS)
    df["is_devanagari"] = df["text"].apply(has_devanagari)
    df["sentiment_score"] = df["text"].apply(score_sentiment)
    df["themes"] = df["text"].apply(tag_themes)
    df["role"] = df["text"].apply(classify_role)
    df.to_csv("comments_tagged.csv", index=False)

    n_unscored = df["sentiment_score"].isna().sum()
    if n_unscored:
        print(f"Note: {n_unscored} Devanagari-script comments left unscored (need a translation step later).\n")

    # Headline metrics use genuine opinions only — excludes viewer Q&A/requests
    # to the creator and comments that couldn't be confidently attributed to
    # one institute. Both columns only exist if you ran clean_raw_comments.py first.
    usable = df["sentiment_score"].notna()
    if "comment_type" in df.columns:
        usable &= df["comment_type"] == "opinion_or_review"
    if "label_status" in df.columns:
        usable &= df["label_status"] != "ambiguous_cross_talk"
    scored = df[usable].copy()
    print(f"Using {len(scored)} of {len(df)} total comments for sentiment metrics "
          f"(excluded unscored / Q&A / ambiguous-institute comments).\n")

    # ---- Metric 1: Sentiment Score by Institute (with reliability flag) ----
    sentiment_by_institute = (
        scored.groupby("institute")["sentiment_score"]
        .agg(avg_sentiment="mean", comment_count="count")
        .reset_index()
    )
    sentiment_by_institute["reliable"] = sentiment_by_institute["comment_count"] >= MIN_COMMENTS_FOR_RANKING
    sentiment_by_institute = sentiment_by_institute.sort_values("avg_sentiment", ascending=False)
    sentiment_by_institute.to_csv("sentiment_by_institute.csv", index=False)

    exploded = scored.explode("themes")
    negative = exploded[exploded["sentiment_score"] < -0.05]

    # ---- Metric 2a: Theme Mention Volume (all comments, any sentiment) ----
    theme_mention_volume = exploded.groupby(["institute", "themes"]).size().reset_index(name="mention_count")
    theme_mention_volume.to_csv("theme_mention_volume.csv", index=False)

    # ---- Metric 2b: Complaint Theme Distribution (negative comments only) ----
    complaint_theme_distribution = negative.groupby(["institute", "themes"]).size().reset_index(name="mention_count")
    complaint_theme_distribution.to_csv("complaint_theme_distribution.csv", index=False)

    # ---- Bonus: Parent vs Student complaints (negative only) ----
    role_theme_breakdown = (
        negative[negative["role"].isin(["parent", "student"])]
        .groupby(["role", "themes"]).size().reset_index(name="mention_count")
    )
    role_theme_breakdown.to_csv("role_theme_breakdown.csv", index=False)

    # ---- Metric 3: Fee vs Sentiment Matrix ----
    try:
        ref = pd.read_csv(INPUT_INSTITUTE_REF)
        fee_vs_sentiment = sentiment_by_institute.merge(ref, on="institute", how="left")
        fee_vs_sentiment["value_score"] = (
            fee_vs_sentiment["avg_sentiment"] / (fee_vs_sentiment["annual_fee"] / 100000)
        ).round(3)
        fee_vs_sentiment.to_csv("fee_vs_sentiment.csv", index=False)
    except FileNotFoundError:
        fee_vs_sentiment = None
        print(f"({INPUT_INSTITUTE_REF} not found — fee_vs_sentiment skipped until you add it)")

    # ---- Metric 4: Sentiment Trend Over Time ----
    scored["published_at"] = pd.to_datetime(scored["published_at"], errors="coerce")
    scored["month"] = scored["published_at"].dt.to_period("M").astype(str)
    sentiment_trend = (
        scored.groupby(["institute", "month"])["sentiment_score"]
        .agg(avg_sentiment="mean", comment_count="count")
        .reset_index()
    )
    sentiment_trend.to_csv("sentiment_trend.csv", index=False)

    # First-half vs second-half comparison per institute (works regardless of exact date span)
    trend_rows = []
    for inst, g in scored.dropna(subset=["published_at"]).groupby("institute"):
        g = g.sort_values("published_at")
        if len(g) < 10:
            continue
        mid = len(g) // 2
        first_half, second_half = g.iloc[:mid]["sentiment_score"].mean(), g.iloc[mid:]["sentiment_score"].mean()
        pct_change = ((second_half - first_half) / abs(first_half)) * 100 if first_half != 0 else np.nan
        trend_rows.append({"institute": inst, "first_half_sentiment": round(first_half, 3),
                            "second_half_sentiment": round(second_half, 3), "pct_change": round(pct_change, 1)})
    pd.DataFrame(trend_rows).to_csv("trend_summary.csv", index=False)

    # ---- Load everything into SQLite ----
    conn = sqlite3.connect(DB_PATH)
    df.assign(themes=df["themes"].apply(str)).to_sql("comments_tagged", conn, if_exists="replace", index=False)
    sentiment_by_institute.to_sql("sentiment_by_institute", conn, if_exists="replace", index=False)
    theme_mention_volume.to_sql("theme_mention_volume", conn, if_exists="replace", index=False)
    complaint_theme_distribution.to_sql("complaint_theme_distribution", conn, if_exists="replace", index=False)
    role_theme_breakdown.to_sql("role_theme_breakdown", conn, if_exists="replace", index=False)
    sentiment_trend.to_sql("sentiment_trend", conn, if_exists="replace", index=False)
    pd.DataFrame(trend_rows).to_sql("trend_summary", conn, if_exists="replace", index=False)
    if fee_vs_sentiment is not None:
        fee_vs_sentiment.to_sql("fee_vs_sentiment", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()

    print("Done. CSVs + coaching_intel.db (SQLite) written.")


if __name__ == "__main__":
    process()
