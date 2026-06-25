"""
Kota Coaching Project — YouTube Comment Collector, BATCH 2 (balancing pass)
-------------------------------------------------------------------------------
Targets ONLY the under-represented institutes from batch 1 (Allen and Vibrant
already have plenty — 385 and 174 comments — so we skip them here).
Goal: more search query variety per institute to close the sample-size gap,
not just more total comments.

Same setup as before — reuse your existing API key.
"""

import time
import pandas as pd
from googleapiclient.discovery import build

API_KEY = "PASTE_YOUR_YOUTUBE_API_KEY_HERE"

INSTITUTES = {
    "Resonance": ["Resonance Kota review", "Resonance Kota experience",
                  "Resonance vs Allen", "Resonance Eduventures Kota",
                  "Resonance Kota hostel review", "Resonance Kota faculty"],
    "Career Point": ["Career Point Kota review", "Career Point Kota experience",
                      "Career Point Gurukul review", "Career Point vs Allen Kota"],
    "Motion Education": ["Motion Kota honest review", "Motion Education Kota experience",
                          "Motion Kota fees review", "Motion vs Allen Kota"],
    "Bansal Classes": ["Bansal Classes Kota experience", "Bansal Classes Kota honest review",
                        "Bansal Classes vs Allen", "Bansal Classes Kota faculty"],
}

MAX_VIDEOS_PER_QUERY = 8
MAX_COMMENTS_PER_VIDEO = 100
OUTPUT_FILE = "kota_coaching_comments_batch2.csv"

youtube = build("youtube", "v3", developerKey=API_KEY)


def search_videos(query, max_results=8):
    request = youtube.search().list(
        q=query, part="id,snippet", type="video",
        maxResults=max_results, relevanceLanguage="en",
    )
    response = request.execute()
    return [{"video_id": i["id"]["videoId"], "title": i["snippet"]["title"],
             "published_at": i["snippet"]["publishedAt"]} for i in response.get("items", [])]


def get_comments(video_id, max_results=100):
    comments = []
    try:
        request = youtube.commentThreads().list(
            part="snippet", videoId=video_id, maxResults=min(max_results, 100),
            textFormat="plainText", order="relevance",
        )
        response = request.execute()
        for item in response.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "video_id": video_id, "comment_id": item["id"],
                "author": top["authorDisplayName"], "text": top["textDisplay"],
                "like_count": top["likeCount"], "published_at": top["publishedAt"],
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
