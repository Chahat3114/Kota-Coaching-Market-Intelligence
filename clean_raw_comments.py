"""
Kota Coaching Market Intelligence — Raw Comment Cleaner
------------------------------------------------------------
Cleans the raw YouTube comment pull before tagging/sentiment analysis:
  1. Drops exact duplicate comments (same comment found via overlapping search queries)
  2. Reconciles institute labels: if a comment clearly names a DIFFERENT
     institute than the one the search query assigned it to, relabel it
     correctly rather than discarding the data
  3. Flags (does not drop) comments that mention 2+ institutes as "ambiguous"
     since they can't be confidently attributed to one institute

Run this BEFORE analyze_comments.py.
"""

import pandas as pd

INPUT = "kota_coaching_comments_raw.csv"
OUTPUT = "kota_coaching_comments_clean.csv"

# Require specific phrases for institutes whose name overlaps common words
# (bare "motion" collides with the physics term — "circular motion" etc.)
ALIASES = {
    "Allen": ["allen"],
    "Resonance": ["resonance"],
    "Motion Education": ["motion kota", "motionite", "motion institute",
                          "motion education", "motion coaching"],
    "Vibrant Academy": ["vibrant"],
    "Bansal Classes": ["bansal"],
    "Career Point": ["career point", "cp gurukul"],
}


def mentioned_institutes(text):
    t = str(text).lower()
    return [inst for inst, kws in ALIASES.items() if any(k in t for k in kws)]


# Heuristic split: a third of real comments turned out to be viewer
# questions/requests to the video creator ("bhaiya pls review motion kota"),
# not opinions about the institute. Flag these rather than scoring them as
# if they were reviews.
REQUEST_MARKERS = ["please", "pls", "plz", "bhaiya", "sir ", "review kar", "review laa",
                    "review do", "which is best", "kaisa h", "kaisi h", "bataiye",
                    "bata do", "suggest", "guide", "best for", "review video"]


def classify_comment_type(text):
    t = str(text).lower()
    if "?" in t or any(m in t for m in REQUEST_MARKERS):
        return "question_or_request"
    return "opinion_or_review"


def reconcile_label(row):
    mentions = row["mentions"]
    if len(mentions) == 0:
        return row["institute"], "kept_original_no_mention"
    if len(mentions) == 1:
        if mentions[0] == row["institute"]:
            return row["institute"], "confirmed_match"
        return mentions[0], "relabeled"
    if row["institute"] in mentions:
        return row["institute"], "confirmed_match_multi_mention"
    return row["institute"], "ambiguous_cross_talk"


def clean():
    df = pd.read_csv(INPUT)
    n_before = len(df)
    df = df.drop_duplicates(subset=["comment_id"]).reset_index(drop=True)
    n_deduped = n_before - len(df)

    df["mentions"] = df["text"].apply(mentioned_institutes)
    results = df.apply(reconcile_label, axis=1)
    df["institute"] = [r[0] for r in results]
    df["label_status"] = [r[1] for r in results]
    df = df.drop(columns=["mentions"])
    df["comment_type"] = df["text"].apply(classify_comment_type)

    print(f"Removed {n_deduped} exact duplicate comments ({n_before} -> {len(df)})")
    print("\nLabel reconciliation breakdown:")
    print(df["label_status"].value_counts().to_string())

    n_ambiguous = (df["label_status"] == "ambiguous_cross_talk").sum()
    print(f"\n{n_ambiguous} comments flagged ambiguous_cross_talk — keep for transparency,")
    print("but exclude from institute-level ranking (filter label_status != 'ambiguous_cross_talk').")

    print("\nComment type breakdown:")
    print(df["comment_type"].value_counts().to_string())
    print("(question_or_request comments are kept in the file but excluded from sentiment metrics)")

    df.to_csv(OUTPUT, index=False)
    print(f"\nSaved cleaned file: {OUTPUT}")
    print("\nInstitute counts AFTER cleaning:")
    print(df["institute"].value_counts().to_string())


if __name__ == "__main__":
    clean()
