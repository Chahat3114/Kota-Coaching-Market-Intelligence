"""
Kota Coaching Institute Project — YouTube Comment Collector
--------------------------------------------------------------
Pulls public YouTube comments about Kota coaching institutes using the
free YouTube Data API v3. No credit card required — 10,000 free quota
units/day.

SETUP (one-time, ~5 minutes):
1. Go to https://console.cloud.google.com/
2. Create a new project (billing NOT required for this API).
3. Search "YouTube Data API v3" in the top search bar -> click Enable.
4. Go to APIs & Services > Credentials > Create Credentials > API key.
5. Copy the key and paste it into API_KEY below.

HOW TO RUN:
- Easiest: open https://colab.research.google.com/, create a new notebook,
  upload this file or paste its contents into a cell, then run it.
- Or locally: pip install google-api-python-client pandas
  then: python collect_youtube_comments.py

IMPORTANT before pushing to GitHub: do NOT commit your real API key.
Replace the key with a placeholder, or load it from an environment
variable (os.environ.get("YOUTUBE_API_KEY")) before committing.
"""

import time
import pandas as pd
from googleapiclient.discovery import build

# ============ CONFIG — edit this section ============
API_KEY = "PASTE_YOUR_YOUTUBE_API_KEY_HERE"

# Institutes and the search queries used to find review/vlog videos.
INSTITUTES = {
    "Allen": ["Allen Kota review", "Allen Career Institute Kota experience"],
    "Resonance": ["Resonance Kota review", "Resonance Eduventures experience"],
    "Motion Education": ["Motion Education Kota review"],
    "Vibrant Academy": ["Vibrant Academy Kota review"],
    "Bansal Classes": ["Bansal Classes Kota review"],
    "Career Point": ["Career Point Kota review"],
}

MAX_VIDEOS_PER_QUERY = 5       # videos pulled per search query
MAX_COMMENTS_PER_VIDEO = 100   # top-level comments pulled per video
OUTPUT_FILE = "kota_coaching_comments_raw.csv"
# ======================================================

youtube = build("youtube", "v3", developerKey=API_KEY)


def search_videos(query, max_results=5):
    """Search YouTube for videos matching a query. Returns list of dicts."""
    request = youtube.search().list(
        q=query,
        part="id,snippet",
        type="video",
        maxResults=max_results,
        relevanceLanguage="en",
    )
    response = request.execute()
    videos = []
    for item in response.get("items", []):
        videos.append({
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"],
        })
    return videos


def get_comments(video_id, max_results=100):
    """Pull top-level comments for one video. Returns list of dicts."""
    comments = []
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100),
            textFormat="plainText",
            order="relevance",
        )
        response = request.execute()
        for item in response.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "video_id": video_id,
                "comment_id": item["id"],
                "author": top["authorDisplayName"],
                "text": top["textDisplay"],
                "like_count": top["likeCount"],
                "published_at": top["publishedAt"],
            })
    except Exception as e:
        print(f"    (skipped — {e})")
    return comments


def collect_all():
    all_rows = []
    for institute, queries in INSTITUTES.items():
        print(f"\n=== {institute} ===")
        for query in queries:
            print(f"Searching: {query}")
            videos = search_videos(query, MAX_VIDEOS_PER_QUERY)
            for v in videos:
                print(f"  Pulling comments: {v['title'][:60]}")
                comments = get_comments(v["video_id"], MAX_COMMENTS_PER_VIDEO)
                for c in comments:
                    c["institute"] = institute
                    c["video_title"] = v["title"]
                    c["video_published_at"] = v["published_at"]
                    all_rows.append(c)
                time.sleep(0.5)
    return pd.DataFrame(all_rows)


if __name__ == "__main__":
    df = collect_all()
    print(f"\nCollected {len(df)} comments across {df['institute'].nunique()} institutes.")
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved to {OUTPUT_FILE}")
