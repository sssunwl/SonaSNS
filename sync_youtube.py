#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SonaSNS — YouTube 頻道成效同步腳本(Phase 1:公開數據)

用 YouTube Data API v3(僅需 API 金鑰,免 OAuth、免頻道擁有者授權)抓取
頻道公開指標,寫進各品牌客戶數據頁(例:okiblues.html)的 youtubeData 區塊。

抓取內容(全為公開數據):
  - 訂閱數、總觀看數、影片總數
  - 最近 N 支影片:標題、發布日、觀看數、按讚數、連結

★ 只有公開指標。觀看維持率、流入來源、可否營利等私有數據需
  YouTube Analytics API + 頻道擁有者 OAuth,屬後續 Phase 3,不在此腳本範圍。

憑證:~/.config/sonasns/youtube.json(絕不放進 repo,repo 是公開 GitHub Pages)
  {
    "api_key": "AIza....",
    "channels": { "okiblues": "okiblues" }   # 品牌代號 -> YouTube handle(不含 @)
  }
CI 環境可改用環境變數 YOUTUBE_API_KEY 覆蓋 api_key。

用法:
  python3 sync_youtube.py              # 同步 config 內全部品牌
  python3 sync_youtube.py okiblues     # 只同步指定品牌
"""

import json
import os
import re
import sys
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_BASE = "https://www.googleapis.com/youtube/v3"
CONFIG_PATH = os.path.expanduser("~/.config/sonasns/youtube.json")
RECENT_VIDEO_COUNT = 6

# 品牌代號 -> 要寫入的 HTML 檔
BRAND_HTML = {
    "okiblues": "okiblues.html",
}


# CI(GitHub Actions)無設定檔時的內建預設 channels
DEFAULT_CHANNELS = {"okiblues": "okiblues"}


def load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    api_key = os.environ.get("YOUTUBE_API_KEY") or cfg.get("api_key")
    if not api_key:
        print(f"❌ 缺少 api_key(環境變數 YOUTUBE_API_KEY 或 {CONFIG_PATH})")
        sys.exit(1)
    channels = cfg.get("channels") or DEFAULT_CHANNELS
    return api_key, channels


def api_get(endpoint, params, api_key):
    params = dict(params)
    params["key"] = api_key
    url = f"{API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"YouTube API {e.code}:{body}") from e


def fetch_channel(handle, api_key):
    """回傳頻道統計 + uploads playlist id。"""
    data = api_get(
        "channels",
        {"part": "snippet,statistics,contentDetails", "forHandle": handle},
        api_key,
    )
    items = data.get("items") or []
    if not items:
        raise RuntimeError(f"找不到頻道 @{handle}(handle 是否正確?)")
    ch = items[0]
    stats = ch.get("statistics", {})
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    return {
        "channelId": ch["id"],
        "title": ch["snippet"]["title"],
        "handle": handle,
        "subscriberCount": int(stats.get("subscriberCount", 0)),
        "hiddenSubscriberCount": stats.get("hiddenSubscriberCount", False),
        "viewCount": int(stats.get("viewCount", 0)),
        "videoCount": int(stats.get("videoCount", 0)),
        "uploads": uploads,
    }


def fetch_recent_videos(uploads_playlist, api_key, n=RECENT_VIDEO_COUNT):
    pl = api_get(
        "playlistItems",
        {"part": "contentDetails", "playlistId": uploads_playlist, "maxResults": n},
        api_key,
    )
    video_ids = [it["contentDetails"]["videoId"] for it in pl.get("items", [])]
    if not video_ids:
        return []
    vids = api_get(
        "videos",
        {"part": "snippet,statistics", "id": ",".join(video_ids)},
        api_key,
    )
    out = []
    for v in vids.get("items", []):
        st = v.get("statistics", {})
        out.append({
            "id": v["id"],
            "title": v["snippet"]["title"],
            "publishedAt": v["snippet"]["publishedAt"][:10],
            "viewCount": int(st.get("viewCount", 0)),
            "likeCount": int(st.get("likeCount", 0)),
        })
    return out


def build_data_object(channel, videos):
    return {
        "channelTitle": channel["title"],
        "handle": channel["handle"],
        "channelUrl": f"https://www.youtube.com/@{channel['handle']}",
        "subscriberCount": channel["subscriberCount"],
        "viewCount": channel["viewCount"],
        "videoCount": channel["videoCount"],
        "updatedAt": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
        "recentVideos": videos,
    }


def update_html(brand, data):
    html_path = BRAND_HTML.get(brand)
    if not html_path or not os.path.exists(html_path):
        print(f"⚠️  {brand}:找不到對應 HTML({html_path}),略過寫入")
        return False
    js = "const youtubeData = " + json.dumps(data, ensure_ascii=False, indent=2) + ";"
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    pattern = r"const youtubeData = \{.*?\};"
    if not re.search(pattern, html, flags=re.DOTALL):
        print(f"⚠️  {html_path} 內找不到 youtubeData 佔位區塊,請確認卡片已插入")
        return False
    new_html = re.sub(pattern, lambda _: js, html, count=1, flags=re.DOTALL)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return new_html != html


def main():
    api_key, channels = load_config()
    only = sys.argv[1] if len(sys.argv) > 1 else None

    changed_any = False
    for brand, handle in channels.items():
        if only and brand != only:
            continue
        print(f"🔄 {brand}(@{handle})…")
        try:
            channel = fetch_channel(handle, api_key)
            videos = fetch_recent_videos(channel["uploads"], api_key)
            data = build_data_object(channel, videos)
            print(f"   訂閱 {data['subscriberCount']:,}・"
                  f"總觀看 {data['viewCount']:,}・影片 {data['videoCount']}・"
                  f"近期 {len(videos)} 支")
            if update_html(brand, data):
                print(f"   ✅ 已更新 {BRAND_HTML.get(brand)}")
                changed_any = True
            else:
                print("   ℹ️ 無變更")
        except Exception as e:
            print(f"   ❌ 失敗:{e}")

    # 鏡射到 Discord #n-sona(失敗不影響同步)
    try:
        from _discord import notify_discord
        notify_discord("🔴 YouTube 頻道成效同步"
                       + ("完成(HTML 已更新)" if changed_any else "完成(無變更)"))
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
