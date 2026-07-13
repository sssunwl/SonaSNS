#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SonaSNS — Google 商家評價同步腳本(Phase 2:Maps 公開數據)

用 Places API (New) 抓 Google 地圖上的公開商家資料,寫進客戶數據頁
(例:okiblues.html)的 googleMapsData 區塊。

抓取內容(全為公開數據):
  - 星等評分(rating)、評論總數(userRatingCount)
  - 最近數則評論(星等、摘要文字、相對時間)
  - 商家名稱、Google Maps 連結

★ 這些是「任何人打開 Google 地圖都看得到」的公開資料,用 API 金鑰即可。
  「有多少人在 Map 上發現你/查路線/打電話」屬 Business Profile Performance API,
  需要店家把你加為擁有者/管理員,屬後續階段,不在此腳本範圍。

⚠️ Places API (New) 需要 Google Cloud 專案「已啟用帳單(billing)」才可呼叫。
   每月有 $200 美金免費額度;一天抓一次遠低於額度,實務上不會產生費用。

憑證:~/.config/sonasns/gmaps.json(絕不放進 repo)
  {
    "api_key": "AIza....",
    "places": {
      "okiblues": {
        "place_id": "",
        "query": "Oki Blues Car Rental 沖繩中文租車 那霸"
      }
    }
  }
  - place_id 留空時,腳本會用 query 自動查出來並印出(建議查到後回填 place_id,較穩定)。
CI 環境可用環境變數 GMAPS_API_KEY 覆蓋 api_key。

用法:
  python3 sync_maps.py            # 同步全部品牌
  python3 sync_maps.py okiblues   # 只同步指定品牌
"""

import json
import os
import re
import sys
import ssl
import urllib.request
from datetime import datetime, timezone

CONFIG_PATH = os.path.expanduser("~/.config/sonasns/gmaps.json")
RECENT_REVIEW_COUNT = 4

BRAND_HTML = {
    "okiblues": "okiblues.html",
}
_CTX = ssl.create_default_context()


# CI(GitHub Actions)無設定檔時的內建預設 places
DEFAULT_PLACES = {
    "okiblues": {
        "place_id": "ChIJ-5MCoQhp5TQRqDzEKluJwss",
        "query": "Oki Blues Car Rental 沖繩中文租車 那霸",
    }
}


def load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    api_key = os.environ.get("GMAPS_API_KEY") or cfg.get("api_key")
    if not api_key:
        print(f"❌ 缺少 api_key(環境變數 GMAPS_API_KEY 或 {CONFIG_PATH})")
        sys.exit(1)
    places = cfg.get("places") or DEFAULT_PLACES
    return api_key, places


def _post(url, body, api_key, field_mask):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    })
    return _read(req)


def _get(url, api_key, field_mask):
    req = urllib.request.Request(url, method="GET", headers={
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    })
    return _read(req)


def _read(req):
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Places API {e.code}:{body}") from e


def resolve_place_id(query, api_key):
    res = _post(
        "https://places.googleapis.com/v1/places:searchText",
        {"textQuery": query, "maxResultCount": 1},
        api_key,
        "places.id,places.displayName",
    )
    places = res.get("places") or []
    if not places:
        raise RuntimeError(f"用 query 找不到店家:{query!r}")
    pid = places[0]["id"]
    name = places[0].get("displayName", {}).get("text", "")
    print(f"   🔎 query 查到 place_id={pid}({name}) — 建議回填到 gmaps.json")
    return pid


def fetch_place(place_id, api_key):
    res = _get(
        f"https://places.googleapis.com/v1/places/{place_id}",
        api_key,
        "id,displayName,rating,userRatingCount,googleMapsUri,reviews",
    )
    reviews = []
    for r in (res.get("reviews") or [])[:RECENT_REVIEW_COUNT]:
        reviews.append({
            "rating": r.get("rating"),
            "text": (r.get("text", {}) or {}).get("text", "").strip(),
            "author": (r.get("authorAttribution", {}) or {}).get("displayName", ""),
            "time": r.get("relativePublishingTimeDescription", ""),
        })
    return {
        "name": (res.get("displayName", {}) or {}).get("text", ""),
        "rating": res.get("rating"),
        "userRatingCount": res.get("userRatingCount", 0),
        "mapsUri": res.get("googleMapsUri", ""),
        "reviews": reviews,
        "updatedAt": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
    }


def update_html(brand, data):
    html_path = BRAND_HTML.get(brand)
    if not html_path or not os.path.exists(html_path):
        print(f"⚠️  {brand}:找不到對應 HTML({html_path}),略過寫入")
        return False
    js = "const googleMapsData = " + json.dumps(data, ensure_ascii=False, indent=2) + ";"
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    pattern = r"const googleMapsData = \{.*?\};"
    if not re.search(pattern, html, flags=re.DOTALL):
        print(f"⚠️  {html_path} 內找不到 googleMapsData 佔位區塊,請確認卡片已插入")
        return False
    new_html = re.sub(pattern, lambda _: js, html, count=1, flags=re.DOTALL)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return new_html != html


def main():
    api_key, places = load_config()
    only = sys.argv[1] if len(sys.argv) > 1 else None

    changed_any = False
    for brand, conf in places.items():
        if only and brand != only:
            continue
        print(f"🔄 {brand}…")
        try:
            place_id = conf.get("place_id") or resolve_place_id(conf.get("query", ""), api_key)
            data = fetch_place(place_id, api_key)
            rating = data["rating"] if data["rating"] is not None else "—"
            print(f"   ⭐ {rating}・評論 {data['userRatingCount']} 則・近期 {len(data['reviews'])} 則摘要")
            if update_html(brand, data):
                print(f"   ✅ 已更新 {BRAND_HTML.get(brand)}")
                changed_any = True
            else:
                print("   ℹ️ 無變更")
        except Exception as e:
            print(f"   ❌ 失敗:{e}")

    try:
        from _discord import notify_discord
        notify_discord("⭐ Google 商家評價同步"
                       + ("完成(HTML 已更新)" if changed_any else "完成(無變更)"))
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
