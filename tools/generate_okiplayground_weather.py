#!/usr/bin/env python3
"""Generate the weekly OKIPLAYGROUND Okinawa forecast graphic and caption.

Uses Open-Meteo's no-key forecast endpoint so the scheduled job has no AI-token
or personal-computer dependency.  Output is designed for GitHub Pages.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "weather"
AI_TEMPLATE = OUTPUT / "assets" / "okiplayground-weekly-template-ai.png"
TZ = ZoneInfo("Asia/Tokyo")
LATITUDE, LONGITUDE = 26.2124, 127.6809  # Okinawa City
WEEKDAYS = "一二三四五六日"


def fetch_forecast() -> list[dict]:
    """Fetch 16 days so a Tuesday run can reliably select the next Wednesday."""
    params = (
        f"latitude={LATITUDE}&longitude={LONGITUDE}&timezone=Asia%2FTokyo"
        "&forecast_days=16"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "apparent_temperature_max,precipitation_probability_max,uv_index_max,"
        "wind_speed_10m_max,wind_gusts_10m_max"
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "SonaSNS-weather-bot/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"無法取得 Open-Meteo 預報：{exc}") from exc

    daily = payload.get("daily", {})
    required = [
        "time", "weather_code", "temperature_2m_max", "temperature_2m_min",
        "apparent_temperature_max", "precipitation_probability_max", "uv_index_max",
        "wind_speed_10m_max", "wind_gusts_10m_max",
    ]
    if any(key not in daily for key in required):
        raise RuntimeError("Open-Meteo 回傳缺少必要的每日預報欄位")
    return [{key: daily[key][i] for key in required} for i in range(len(daily["time"]))]


def next_wednesday(today: date) -> date:
    return today + timedelta(days=(2 - today.weekday()) % 7)


def weather_label(code: int) -> tuple[str, str]:
    if code == 0:
        return "晴朗", "sun"
    if code in (1, 2):
        return "晴時多雲", "partly"
    if code == 3:
        return "多雲", "cloud"
    if code in (45, 48):
        return "有霧", "fog"
    if code in (51, 53, 55, 56, 57):
        return "毛毛雨", "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "有陣雨", "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "有降雪", "snow"
    if code in (95, 96, 99):
        return "雷陣雨", "storm"
    return "天氣變化", "cloud"


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


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        os.getenv("WEATHER_FONT", ""),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Bold.otf" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size, index=0)
    return ImageFont.load_default()


def centered(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, fnt, fill, anchor="mm"):
    draw.text(xy, text, font=fnt, fill=fill, anchor=anchor)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_sun(draw, x, y, size):
    for i in range(8):
        angle = math.pi * 2 * i / 8
        x1, y1 = x + math.cos(angle) * size * .76, y + math.sin(angle) * size * .76
        x2, y2 = x + math.cos(angle) * size, y + math.sin(angle) * size
        draw.line((x1, y1, x2, y2), fill="#ffad13", width=max(3, size // 12))
    draw.ellipse((x-size*.58, y-size*.58, x+size*.58, y+size*.58), fill="#ffc831", outline="#f39b08", width=3)


def draw_cloud(draw, x, y, size, rain=False, storm=False):
    cloud = "#d9e5ed"
    edge = "#9aacb9"
    draw.ellipse((x-size*.78, y-size*.18, x-size*.1, y+size*.42), fill=cloud, outline=edge, width=2)
    draw.ellipse((x-size*.35, y-size*.5, x+size*.38, y+size*.42), fill=cloud, outline=edge, width=2)
    draw.ellipse((x, y-size*.25, x+size*.8, y+size*.42), fill=cloud, outline=edge, width=2)
    draw.rounded_rectangle((x-size*.78, y+size*.02, x+size*.82, y+size*.45), radius=size*.18, fill=cloud, outline=edge, width=2)
    if storm:
        draw.polygon([(x+size*.05, y+size*.42), (x-size*.18, y+size*.95), (x+size*.08, y+size*.92), (x-size*.02, y+size*1.4), (x+size*.43, y+size*.75), (x+size*.16, y+size*.78)], fill="#ffb000")
    if rain:
        for dx in (-.38, 0, .38):
            draw.line((x+size*dx, y+size*.67, x+size*(dx-.08), y+size*1.05), fill="#248bdb", width=max(3, size//10))


def draw_condition(draw, x, y, kind, size=42):
    if kind == "sun":
        draw_sun(draw, x, y, size)
    elif kind == "partly":
        draw_sun(draw, x-size*.25, y-size*.2, int(size*.75))
        draw_cloud(draw, x+size*.12, y+size*.08, size*.8)
    elif kind in ("rain", "drizzle"):
        draw_cloud(draw, x, y, size, rain=True)
    elif kind == "storm":
        draw_cloud(draw, x, y, size, rain=True, storm=True)
    else:
        draw_cloud(draw, x, y, size)


def generate_image(days: list[dict], target: Path) -> None:
    """Fill an AI-illustrated poster background with deterministic forecast data."""
    if not AI_TEMPLATE.exists():
        raise RuntimeError(f"找不到 AI 天氣模板：{AI_TEMPLATE}")
    days = days[:7]
    width, height = 1080, 1440
    image = Image.open(AI_TEMPLATE).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    navy, red, orange = "#092e74", "#ed2524", "#f18622"
    # Header: the AI template intentionally has no text, so Traditional Chinese stays correct every week.
    draw.ellipse((48, 28, 118, 98), fill="#fff5bd", outline=navy, width=3)
    draw.arc((58, 43, 108, 88), 200, 335, fill="#22a8d6", width=8)
    draw.arc((57, 33, 108, 73), 205, 325, fill="#ee5540", width=4)
    centered(draw, (83, 114), "OKIPLAYGROUND", font(12, True), navy)
    centered(draw, (540, 82), "沖繩", font(57, True), navy)
    centered(draw, (700, 82), "7", font(78, True), red)
    centered(draw, (862, 82), "天天氣預報", font(57, True), navy)
    centered(draw, (610, 198), "一週天氣早知道，輕鬆安排沖繩行程！", font(24, True), navy)

    card_w, gap, start_x, y = 134, 17, 25, 246
    for idx, day in enumerate(days):
        x = start_x + idx * (card_w + gap)
        dt = date.fromisoformat(day["time"])
        weekday = WEEKDAYS[dt.weekday()]
        centered(draw, (x+card_w/2, y+34), f"{dt.month}/{dt.day}", font(29, True), "#ffffff")
        centered(draw, (x+card_w/2, y+76), f"星期{weekday}", font(20, True), red if weekday in "六日" else "#ffffff")
        label, kind = weather_label(int(day["weather_code"]))
        draw_condition(draw, x+card_w/2, y+180, kind, 31)
        centered(draw, (x+card_w/2, y+284), label, font(19, True), navy)
        centered(draw, (x+card_w/2, y+354), f"{round(day['temperature_2m_max'])}°", font(42, True), red)
        centered(draw, (x+card_w/2, y+408), f"{round(day['temperature_2m_min'])}°", font(35, True), "#1760bd")
        centered(draw, (x+card_w/2, y+488), f"雨 {round(day['precipitation_probability_max'])}%", font(21, True), navy)
        centered(draw, (x+card_w/2, y+522), "降雨機率", font(15, True), navy)
        centered(draw, (x+card_w/2, y+585), f"UV {day['uv_index_max']:.1f}", font(19, True), navy)
        uv_fill = "#ef7c22" if day["uv_index_max"] >= 8 else "#63be36" if day["uv_index_max"] >= 6 else "#ffc31b"
        rounded(draw, (x+15, y+608, x+card_w-15, y+634), 10, uv_fill)
        centered(draw, (x+card_w/2, y+621), uv_label(day["uv_index_max"]), font(14, True), "#ffffff")
        centered(draw, (x+card_w/2, y+688), f"風 {round(day['wind_speed_10m_max'])} km/h", font(16, True), navy)
        clothing = "短袖＋雨具" if day["precipitation_probability_max"] >= 40 else "短袖＋防曬"
        centered(draw, (x+card_w/2, y+760), clothing, font(16, True), navy)

    rainiest = max(days, key=lambda x: x["precipitation_probability_max"])
    hottest = max(days, key=lambda x: x["temperature_2m_max"])
    windiest = max(days, key=lambda x: x["wind_gusts_10m_max"])
    sunniest = min(days, key=lambda x: (x["precipitation_probability_max"], x["weather_code"]))
    notes = [
        ("行程", f"{date.fromisoformat(sunniest['time']).month}/{date.fromisoformat(sunniest['time']).day}相對穩定", "戶外行程優先"),
        ("雨具", f"最高 {round(rainiest['precipitation_probability_max'])}%", "折傘記得帶"),
        ("防曬", f"最高 {round(hottest['temperature_2m_max'])}°C", "補水、防曬"),
        ("海況", f"陣風 {round(windiest['wind_gusts_10m_max'])} km/h", "海上活動看公告"),
    ]
    centered(draw, (125, 1078), "本週沖繩旅遊觀察", font(28, True), navy, "lm")
    for i, (tag, line1, line2) in enumerate(notes):
        cx = 175 + i * 255
        rounded(draw, (cx-40, 1110, cx+40, 1142), 12, "#fff1df", outline=orange, width=1)
        centered(draw, (cx, 1126), tag, font(15, True), orange)
        centered(draw, (cx, 1174), line1, font(16, True), navy)
        centered(draw, (cx, 1205), line2, font(15), "#42607d")
        if i < 3:
            draw.line((cx+127, 1100, cx+127, 1215), fill="#d3dce6", width=1)
    centered(draw, (590, 1283), "沖繩小知識  ·  夏日旅遊提醒", font(29, True), red)
    centered(draw, (590, 1326), "紫外線強、午後天氣變化快；就算多雲也別省略防曬。", font(20, True), navy)
    centered(draw, (590, 1360), "出門前準備：防曬乳　帽子　太陽眼鏡　飲用水　折疊傘", font(20, True), navy)
    centered(draw, (590, 1392), "海上活動與船班請以當天業者公告為準。", font(18), navy)
    centered(draw, (width/2, 1412), "資料：Open-Meteo 預報模型｜" + datetime.now(TZ).strftime("%Y/%m/%d %H:%M JST"), font(14), "#42607d")
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "PNG", optimize=True)


def make_caption(days: list[dict]) -> str:
    period_start, period_end = date.fromisoformat(days[0]["time"]), date.fromisoformat(days[-1]["time"])
    sunniest = min(days, key=lambda x: (x["precipitation_probability_max"], x["weather_code"]))
    rainy_days = [d for d in days if d["precipitation_probability_max"] >= 50 or d["weather_code"] >= 80]
    hottest = max(days, key=lambda x: x["apparent_temperature_max"])
    windiest = max(days, key=lambda x: x["wind_gusts_10m_max"])
    season = "盛夏" if period_start.month in (7, 8, 9) else "初夏" if period_start.month in (5, 6) else "旅遊旺季"
    title = "🌦️ 陽光與驟雨交織：一週天氣速報 ☀️🌺" if rainy_days else "☀️ 陽光主場的一週：天氣速報 🌺"
    rainy_text = "後半週有局部陣雨變數" if rainy_days else "整週以穩定天氣為主"
    sun_date = date.fromisoformat(sunniest["time"])
    hot_line = f"🥵 防曬抗暑不能少：最高體感約 {round(hottest['apparent_temperature_max'])}°C，帽子、墨鏡和補水都是出門標配。"
    wind_line = (f"🌬️ 留意海上活動：最大陣風可能到 {round(windiest['wind_gusts_10m_max'])} km/h，潛水、SUP 與船班請以業者當日公告為準。"
                 if windiest["wind_gusts_10m_max"] >= 30 else
                 "🌊 海上活動仍要看當日海況：海島午後變化快，下水與搭船前請確認業者公告。")
    return "\n\n".join([
        title,
        f"島上{season}模式持續發威，白天高溫約 {round(min(d['temperature_2m_max'] for d in days))}～{round(max(d['temperature_2m_max'] for d in days))}°C。{rainy_text}，出門在外記得在防曬與防雨模式之間隨時切換。💦🕶️✨",
        "\n".join([
            (f"☀️ 優先排戶外的一天：{sun_date.month}/{sun_date.day} 降雨機率約 {round(sunniest['precipitation_probability_max'])}%，想衝海邊或水上行程可優先考慮這天。"
             if sunniest["precipitation_probability_max"] < 50 else
             f"🌦️ 相對穩定的一天：{sun_date.month}/{sun_date.day} 降雨機率約 {round(sunniest['precipitation_probability_max'])}%，仍建議保留室內備案再出發。"),
            (f"⚡ 雨具記得隨身帶：{len(rainy_days)} 天降雨機率偏高，午後短暫陣雨或雷雨都有可能。" if rainy_days else "🌤️ 行程彈性更高：降雨機率整體不高，戶外行程可以放心安排。"),
            hot_line,
            wind_line,
        ]),
        "想掌握此時各景點哪裡正出大太陽、哪裡剛下完暴雨的即時情報，歡迎進社團看現場回報 👀\n👉 https://www.facebook.com/groups/okiplayground/\n\n#沖繩遊樂園 #OKIPLAYGROUND #沖繩天氣 #沖繩旅遊 #沖繩自由行",
    ])


def write_page(days: list[dict], generated_at: str, image_name: str) -> None:
    rows = []
    for item in days:
        dt = date.fromisoformat(item["time"])
        label, _ = weather_label(int(item["weather_code"]))
        rows.append(f"<tr><td>{dt.month}/{dt.day}（週{WEEKDAYS[dt.weekday()]}）</td><td>{label}</td><td>{round(item['temperature_2m_max'])}° / {round(item['temperature_2m_min'])}°</td><td>{round(item['precipitation_probability_max'])}%</td><td>{item['uv_index_max']:.1f}</td></tr>")
    html = f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OKIPLAYGROUND｜沖繩一週天氣速報</title><style>body{{margin:0;background:#e3f6ff;color:#082d72;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif}}main{{max-width:900px;margin:auto;padding:32px 18px 60px}}section{{background:#fff;border-radius:20px;padding:22px;margin:18px 0;box-shadow:0 5px 18px #6094aa33}}h1{{margin:.1em 0;text-align:center}}.sub{{text-align:center;color:#42607d}}img{{width:100%;border-radius:14px}}a.button{{display:inline-block;background:#ed2524;color:white;padding:12px 20px;border-radius:99px;text-decoration:none;font-weight:700;margin:4px 6px 4px 0}}pre{{white-space:pre-wrap;font:15px/1.75 inherit;color:#243a56;background:#f3f8fb;padding:18px;border-radius:12px}}table{{width:100%;border-collapse:collapse;color:#243a56}}td,th{{padding:9px;border-bottom:1px solid #dae5ea;text-align:left}}small{{color:#58718a}}</style><main><h1>🌺 OKIPLAYGROUND 沖繩一週天氣速報</h1><p class="sub">每週二 01:58（JST）自動更新｜本次生成：{generated_at}</p><section><img src="{image_name}" alt="沖繩七日天氣預報"><p><a class="button" href="{image_name}" download>下載預報圖 PNG</a><a class="button" href="caption.txt" download>下載帖文 TXT</a></p></section><section><h2>可直接貼上的文案</h2><pre>{make_caption(days)}</pre></section><section><h2>每日資料</h2><table><tr><th>日期</th><th>天氣</th><th>高／低溫</th><th>降雨</th><th>UV</th></tr>{''.join(rows)}</table><p><small>資料來源：Open-Meteo 預報模型（沖繩市）。預報會隨每日模型更新而變動；海況、警報與颱風資訊請另以日本氣象廳及業者公告確認。</small></p></section></main></html>'''
    (OUTPUT / "index.html").write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", help="Test date in YYYY-MM-DD (JST)")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else datetime.now(TZ).date()
    start = next_wednesday(today)
    all_days = fetch_forecast()
    forecast = [item for item in all_days if start <= date.fromisoformat(item["time"]) <= start + timedelta(days=7)]
    if len(forecast) != 8:
        raise RuntimeError(f"預報資料不足：需要 {start} 起 8 天，取得 {len(forecast)} 天")
    OUTPUT.mkdir(exist_ok=True)
    stamp = f"{forecast[0]['time']}_to_{forecast[-1]['time']}"
    dated_image = OUTPUT / f"okinawa-weather-{stamp}.png"
    generate_image(forecast[:7], dated_image)
    shutil.copy2(dated_image, OUTPUT / "current.png")
    caption = make_caption(forecast)
    (OUTPUT / f"caption-{stamp}.txt").write_text(caption + "\n", encoding="utf-8")
    (OUTPUT / "caption.txt").write_text(caption + "\n", encoding="utf-8")
    metadata = {"generated_at": datetime.now(TZ).isoformat(), "provider": "Open-Meteo", "location": "Okinawa City", "days": forecast}
    (OUTPUT / "weather.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_page(forecast, datetime.now(TZ).strftime("%Y/%m/%d %H:%M JST"), dated_image.name)
    print(f"Generated {dated_image.relative_to(ROOT)} and weather/index.html")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
