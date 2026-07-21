#!/usr/bin/env python3
"""Publish weekly Okinawa forecast facts, post copy, and an image-generation prompt.

The final visual is intentionally made in ChatGPT with the owner's supplied
reference image. This avoids unreliable AI-rendered Traditional Chinese and
keeps the established OKIPLAYGROUND poster design under human review.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "weather"
TZ = ZoneInfo("Asia/Tokyo")
LATITUDE, LONGITUDE = 26.2124, 127.6809  # Okinawa City
WEEKDAYS = "一二三四五六日"


def fetch_forecast() -> list[dict]:
    params = (
        f"latitude={LATITUDE}&longitude={LONGITUDE}&timezone=Asia%2FTokyo"
        "&forecast_days=16"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "apparent_temperature_max,precipitation_probability_max,uv_index_max,"
        "wind_speed_10m_max,wind_gusts_10m_max"
    )
    request = urllib.request.Request(
        f"https://api.open-meteo.com/v1/forecast?{params}",
        headers={"User-Agent": "SonaSNS-weather-bot/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"無法取得 Open-Meteo 預報：{exc}") from exc
    daily = payload.get("daily", {})
    fields = [
        "time", "weather_code", "temperature_2m_max", "temperature_2m_min",
        "apparent_temperature_max", "precipitation_probability_max", "uv_index_max",
        "wind_speed_10m_max", "wind_gusts_10m_max",
    ]
    if any(field not in daily for field in fields):
        raise RuntimeError("Open-Meteo 回傳缺少必要的每日預報欄位")
    return [{field: daily[field][i] for field in fields} for i in range(len(daily["time"]))]


def next_wednesday(today: date) -> date:
    return today + timedelta(days=(2 - today.weekday()) % 7)


def weather_label(code: int) -> str:
    if code == 0:
        return "晴朗"
    if code in (1, 2):
        return "晴時多雲"
    if code == 3:
        return "多雲"
    if code in (45, 48):
        return "有霧"
    if code in (51, 53, 55, 56, 57):
        return "毛毛雨"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "有陣雨"
    if code in (71, 73, 75, 77, 85, 86):
        return "有降雪"
    if code in (95, 96, 99):
        return "雷陣雨"
    return "天氣變化"


def uv_label(value: float) -> str:
    if value < 3:
        return "低"
    if value < 6:
        return "中等"
    if value < 8:
        return "高"
    if value < 11:
        return "很高"
    return "極高"


def day_line(day: dict) -> str:
    dt = date.fromisoformat(day["time"])
    return (
        f"{dt.month}/{dt.day}（星期{WEEKDAYS[dt.weekday()]}）：{weather_label(int(day['weather_code']))}；"
        f"{round(day['temperature_2m_max'])}°C / {round(day['temperature_2m_min'])}°C；"
        f"降雨 {round(day['precipitation_probability_max'])}%；UV {day['uv_index_max']:.1f}（{uv_label(day['uv_index_max'])}）；"
        f"風 {round(day['wind_speed_10m_max'])} km/h"
    )


def make_post(days: list[dict]) -> str:
    sunniest = min(days, key=lambda item: (item["precipitation_probability_max"], item["weather_code"]))
    rainy_days = [item for item in days if item["precipitation_probability_max"] >= 50 or item["weather_code"] >= 80]
    hottest = max(days, key=lambda item: item["apparent_temperature_max"])
    windiest = max(days, key=lambda item: item["wind_gusts_10m_max"])
    sunny_date = date.fromisoformat(sunniest["time"])
    month = date.fromisoformat(days[0]["time"]).month
    season = "盛夏" if month in (7, 8, 9) else "初夏" if month in (5, 6) else "旅遊旺季"
    first_tip = (
        f"☀️ 優先排戶外的一天：{sunny_date.month}/{sunny_date.day} 降雨機率約 {round(sunniest['precipitation_probability_max'])}%，想衝海邊或水上行程可優先考慮這天。"
        if sunniest["precipitation_probability_max"] < 50
        else f"🌦️ 相對穩定的一天：{sunny_date.month}/{sunny_date.day} 降雨機率約 {round(sunniest['precipitation_probability_max'])}%，仍建議保留室內備案再出發。"
    )
    rain_tip = (
        f"⚡ 雨具記得隨身帶：{len(rainy_days)} 天降雨機率偏高，午後短暫陣雨或雷雨都有可能。"
        if rainy_days else "🌤️ 行程彈性更高：降雨機率整體不高，戶外行程可以放心安排。"
    )
    wind_tip = (
        f"🌬️ 留意海上活動：最大陣風可能到 {round(windiest['wind_gusts_10m_max'])} km/h，潛水、SUP 與船班請以業者當日公告為準。"
        if windiest["wind_gusts_10m_max"] >= 30 else "🌊 海上活動仍要看當日海況：海島午後變化快，下水與搭船前請確認業者公告。"
    )
    return "\n\n".join([
        "🌦️ 陽光與驟雨交織：一週天氣速報 ☀️🌺" if rainy_days else "☀️ 陽光主場的一週：天氣速報 🌺",
        f"島上{season}模式持續發威，白天高溫約 {round(min(item['temperature_2m_max'] for item in days))}～{round(max(item['temperature_2m_max'] for item in days))}°C。出門在外記得在防曬與防雨模式之間隨時切換。💦🕶️✨",
        "\n".join([
            first_tip,
            rain_tip,
            f"🥵 防曬抗暑不能少：最高體感約 {round(hottest['apparent_temperature_max'])}°C，帽子、墨鏡和補水都是出門標配。",
            wind_tip,
        ]),
        "想掌握此時各景點哪裡正出大太陽、哪裡剛下完暴雨的即時情報，歡迎進社團看現場回報 👀\n👉 https://www.facebook.com/groups/okiplayground/\n\n#沖繩遊樂園 #OKIPLAYGROUND #沖繩天氣 #沖繩旅遊 #沖繩自由行",
    ])


def make_image_prompt(days: list[dict]) -> str:
    rainiest = max(days, key=lambda item: item["precipitation_probability_max"])
    hottest = max(days, key=lambda item: item["temperature_2m_max"])
    windiest = max(days, key=lambda item: item["wind_gusts_10m_max"])
    sunniest = min(days, key=lambda item: (item["precipitation_probability_max"], item["weather_code"]))
    date_range = f"{date.fromisoformat(days[0]['time']).month}/{date.fromisoformat(days[0]['time']).day}～{date.fromisoformat(days[-1]['time']).month}/{date.fromisoformat(days[-1]['time']).day}"
    daily = "\n".join(f"- {day_line(day)}" for day in days)
    return f'''我會附上一張 OKIPLAYGROUND「沖繩 7 天天氣預報」的範例圖。請嚴格以它作為版型、插畫風格、色彩、字級階層、七欄排列、扶桑花、棕櫚葉、海洋底圖與下方兩個資訊框的唯一視覺參考，製作一張新的 1080×1440 直式 PNG。

請保留範例圖的 OKIPLAYGROUND 海豚 Logo、主標題「沖繩 7 天天氣預報」、副標題「一週天氣早知道，輕鬆安排沖繩行程！」，不要更換品牌設計。所有文字必須是清楚、正確的繁體中文；不要加入英文亂碼、錯字、浮水印或額外資料來源。

這次的 7 欄日期與資料必須逐字依下列內容填入（由左至右）：
{daily}

每一欄依天氣畫對應圖示，並保留：日期／星期、天氣描述、紅色高溫、藍色低溫、降雨機率、UV 數字與等級色條、風速、短袖＋雨具或短袖＋防曬的建議。星期六與星期日使用紅色星期字。

底部「本週沖繩旅遊觀察」請濃縮成四項：
1. {date.fromisoformat(sunniest['time']).month}/{date.fromisoformat(sunniest['time']).day}相對適合戶外行程（降雨 {round(sunniest['precipitation_probability_max'])}%）
2. 最高降雨機率 {round(rainiest['precipitation_probability_max'])}%：折疊傘隨身帶
3. 最高氣溫 {round(hottest['temperature_2m_max'])}°C：補水、防曬
4. 最大陣風 {round(windiest['wind_gusts_10m_max'])} km/h：海上活動看業者公告

底部「沖繩小知識」維持範例圖的夏日旅遊提醒主題：紫外線強、午後天氣變化快；準備防曬乳、帽子、太陽眼鏡、飲用水與折疊傘。不要自行猜測或改動上面提供的天氣數字。'''


def write_page(days: list[dict], generated_at: str, post: str, prompt: str) -> None:
    table_rows = "".join(
        f"<tr><td>{html.escape(day_line(day).replace('：', '｜', 1))}</td></tr>" for day in days
    )
    page = f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OKIPLAYGROUND｜沖繩一週天氣速報</title><style>body{{margin:0;background:#e3f6ff;color:#082d72;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif}}main{{max-width:900px;margin:auto;padding:32px 18px 60px}}section{{background:#fff;border-radius:20px;padding:22px;margin:18px 0;box-shadow:0 5px 18px #6094aa33}}h1{{margin:.1em 0;text-align:center}}.sub{{text-align:center;color:#42607d}}a.button{{display:inline-block;background:#ed2524;color:white;padding:12px 20px;border-radius:99px;text-decoration:none;font-weight:700;margin:4px 6px 4px 0}}pre{{white-space:pre-wrap;font:15px/1.75 inherit;color:#243a56;background:#f3f8fb;padding:18px;border-radius:12px}}table{{width:100%;border-collapse:collapse;color:#243a56}}td{{padding:10px;border-bottom:1px solid #dae5ea}}small{{color:#58718a}}</style><main><h1>🌺 OKIPLAYGROUND 沖繩一週天氣速報</h1><p class="sub">每週二 01:58（JST）自動更新｜本次生成：{generated_at}</p><section><h2>可直接貼上的帖文</h2><p><a class="button" href="post.txt" download>下載帖文 TXT</a><a class="button" href="image-prompt.txt" download>下載 ChatGPT 圖片 Prompt</a></p><pre>{html.escape(post)}</pre></section><section><h2>給 ChatGPT 的圖片生成 Prompt</h2><p>附上你的範例圖，再完整貼上以下內容。</p><pre>{html.escape(prompt)}</pre></section><section><h2>本週天氣資料</h2><table>{table_rows}</table><p><small>資料來源：Open-Meteo 預報模型（沖繩市）。海況、警報與颱風資訊請另以日本氣象廳及業者公告確認。</small></p></section></main></html>'''
    (OUTPUT / "index.html").write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", help="Test date in YYYY-MM-DD (JST)")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else datetime.now(TZ).date()
    start = next_wednesday(today)
    forecast = [
        item for item in fetch_forecast()
        if start <= date.fromisoformat(item["time"]) <= start + timedelta(days=6)
    ]
    if len(forecast) != 7:
        raise RuntimeError(f"預報資料不足：需要 {start} 起 7 天，取得 {len(forecast)} 天")
    OUTPUT.mkdir(exist_ok=True)
    stamp = f"{forecast[0]['time']}_to_{forecast[-1]['time']}"
    post, prompt = make_post(forecast), make_image_prompt(forecast)
    for filename, content in {
        "post.txt": post,
        f"post-{stamp}.txt": post,
        "image-prompt.txt": prompt,
        f"image-prompt-{stamp}.txt": prompt,
    }.items():
        (OUTPUT / filename).write_text(content + "\n", encoding="utf-8")
    metadata = {"generated_at": datetime.now(TZ).isoformat(), "provider": "Open-Meteo", "location": "Okinawa City", "days": forecast}
    (OUTPUT / "weather.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_page(forecast, datetime.now(TZ).strftime("%Y/%m/%d %H:%M JST"), post, prompt)
    print(f"Generated weekly weather post and image prompt for {stamp}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
