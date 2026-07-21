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
    width, height = 1600, 2000
    image = Image.new("RGB", (width, height), "#dff5ff")
    draw = ImageDraw.Draw(image)
    # Tropical sky + sea bands.
    for y in range(height):
        if y < 360:
            blend = y / 360
            color = (int(225 - 20*blend), int(247 - 8*blend), 255)
        else:
            blend = min(1, (y - 360) / (height - 360))
            color = (int(200 - 15*blend), int(240 + 10*blend), int(249 + 4*blend))
        draw.line((0, y, width, y), fill=color)
    for x in range(-100, width + 200, 110):
        draw.arc((x, 1690, x+280, 1940), 200, 340, fill="#b2e9ed", width=5)

    navy, red, orange = "#092e74", "#ed2524", "#f18622"
    centered(draw, (width/2, 95), "OKIPLAYGROUND", font(44, True), navy)
    centered(draw, (535, 178), "沖繩", font(78, True), navy)
    centered(draw, (800, 178), "8", font(106, True), red)
    centered(draw, (1088, 178), "日天氣預報", font(78, True), navy)
    rounded(draw, (140, 250, 1460, 326), 34, "#ffffff", outline=navy, width=3)
    centered(draw, (width/2, 289), "一週天氣早知道，輕鬆安排沖繩行程！", font(32, True), navy)
    draw_sun(draw, 132, 90, 27)
    # Decorative leaves.
    for i in range(6):
        draw.line((1420, 0, 1350-i*23, 35+i*25), fill="#338955", width=9)

    card_w, card_h = 350, 560
    x_positions, y_positions = [55, 445, 835, 1225], [385, 990]
    for idx, day in enumerate(days):
        x, y = x_positions[idx % 4], y_positions[idx // 4]
        rounded(draw, (x, y, x+card_w, y+card_h), 28, "#ffffff", outline="#b9d4e6", width=3)
        rounded(draw, (x, y, x+card_w, y+110), 28, navy)
        draw.rectangle((x, y+70, x+card_w, y+110), fill=navy)
        dt = date.fromisoformat(day["time"])
        weekday = WEEKDAYS[dt.weekday()]
        centered(draw, (x+card_w/2, y+43), f"{dt.month}/{dt.day}", font(42, True), "#ffffff")
        centered(draw, (x+card_w/2, y+82), f"星期{weekday}", font(27, True), red if weekday in "六日" else "#ffffff")
        label, kind = weather_label(int(day["weather_code"]))
        draw_condition(draw, x+card_w/2, y+190, kind, 52)
        centered(draw, (x+card_w/2, y+305), label, font(31, True), navy)
        centered(draw, (x+card_w/2, y+365), f"{round(day['temperature_2m_max'])}°C", font(58, True), red)
        centered(draw, (x+card_w/2, y+423), f"{round(day['temperature_2m_min'])}°C", font(48, True), "#1760bd")
        draw.line((x+35, y+462, x+card_w-35, y+462), fill="#d8e2e8", width=2)
        centered(draw, (x+card_w/2, y+494), f"降雨機率 {round(day['precipitation_probability_max'])}%", font(25, True), navy)
        centered(draw, (x+card_w/2, y+531), f"UV {day['uv_index_max']:.1f} · {uv_label(day['uv_index_max'])}", font(23, True), "#42607d")

    rounded(draw, (55, 1605, 1545, 1910), 28, "#ffffff", outline=navy, width=4)
    centered(draw, (130, 1660), "本週沖繩旅遊觀察", font(38, True), navy, "lm")
    rainiest = max(days, key=lambda x: x["precipitation_probability_max"])
    hottest = max(days, key=lambda x: x["temperature_2m_max"])
    windiest = max(days, key=lambda x: x["wind_gusts_10m_max"])
    sunniest = min(days, key=lambda x: (x["precipitation_probability_max"], x["weather_code"]))
    notes = [
        ("行程", f"{date.fromisoformat(sunniest['time']).month}/{date.fromisoformat(sunniest['time']).day}較適合戶外行程", "行程建議"),
        ("雨具", f"最高降雨機率 {round(rainiest['precipitation_probability_max'])}%", "雨具隨身帶"),
        ("防曬", f"最高 {round(hottest['temperature_2m_max'])}°C／體感注意補水", "防曬防中暑"),
        ("海況", f"最大陣風 {round(windiest['wind_gusts_10m_max'])} km/h", "海上活動看公告"),
    ]
    for i, (tag, line1, line2) in enumerate(notes):
        cx = 230 + i * 365
        rounded(draw, (cx-55, 1712, cx+55, 1764), 18, "#fff1df", outline=orange, width=2)
        centered(draw, (cx, 1739), tag, font(22, True), orange)
        centered(draw, (cx, 1810), line1, font(25, True), navy)
        centered(draw, (cx, 1850), line2, font(24), "#42607d")
        if i < 3:
            draw.line((cx+175, 1705, cx+175, 1870), fill="#d3dce6", width=2)
    centered(draw, (width/2, 1950), "資料：Open-Meteo 預報模型｜生成時間：" + datetime.now(TZ).strftime("%Y/%m/%d %H:%M JST"), font(20), "#42607d")
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
    html = f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OKIPLAYGROUND｜沖繩一週天氣速報</title><style>body{{margin:0;background:#e3f6ff;color:#082d72;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif}}main{{max-width:900px;margin:auto;padding:32px 18px 60px}}section{{background:#fff;border-radius:20px;padding:22px;margin:18px 0;box-shadow:0 5px 18px #6094aa33}}h1{{margin:.1em 0;text-align:center}}.sub{{text-align:center;color:#42607d}}img{{width:100%;border-radius:14px}}a.button{{display:inline-block;background:#ed2524;color:white;padding:12px 20px;border-radius:99px;text-decoration:none;font-weight:700;margin:4px 6px 4px 0}}pre{{white-space:pre-wrap;font:15px/1.75 inherit;color:#243a56;background:#f3f8fb;padding:18px;border-radius:12px}}table{{width:100%;border-collapse:collapse;color:#243a56}}td,th{{padding:9px;border-bottom:1px solid #dae5ea;text-align:left}}small{{color:#58718a}}</style><main><h1>🌺 OKIPLAYGROUND 沖繩一週天氣速報</h1><p class="sub">每週二 01:58（JST）自動更新｜本次生成：{generated_at}</p><section><img src="{image_name}" alt="沖繩八日天氣預報"><p><a class="button" href="{image_name}" download>下載預報圖 PNG</a><a class="button" href="caption.txt" download>下載帖文 TXT</a></p></section><section><h2>可直接貼上的文案</h2><pre>{make_caption(days)}</pre></section><section><h2>每日資料</h2><table><tr><th>日期</th><th>天氣</th><th>高／低溫</th><th>降雨</th><th>UV</th></tr>{''.join(rows)}</table><p><small>資料來源：Open-Meteo 預報模型（沖繩市）。預報會隨每日模型更新而變動；海況、警報與颱風資訊請另以日本氣象廳及業者公告確認。</small></p></section></main></html>'''
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
    generate_image(forecast, dated_image)
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
