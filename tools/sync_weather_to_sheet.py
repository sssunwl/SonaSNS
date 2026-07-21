#!/usr/bin/env python3
"""Write the generated weekly weather post into its one matching OKIP Sheet row.

This is deliberately narrower than the normal drafting tool: it can only touch
the current generated weather row, and it refuses to continue unless exactly
one matching row is found.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import gspread


ROOT = Path(__file__).resolve().parents[1]
WEATHER = ROOT / "weather"
SHEET_ID = "1gTbG5il6CtomkTfRXmFXwx7_4AIG8CjOnfsdoRynuS4"


def worksheet():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        client = gspread.service_account_from_dict(json.loads(raw))
    else:
        credentials = Path.home() / ".config" / "sonasns" / "credentials.json"
        if not credentials.exists():
            raise RuntimeError("缺少 GOOGLE_SERVICE_ACCOUNT_JSON 或本機 sonasns 憑證")
        client = gspread.service_account(filename=str(credentials))
    return client.open_by_key(SHEET_ID).sheet1


def load_generated() -> tuple[dict, str, str]:
    metadata = json.loads((WEATHER / "weather.json").read_text(encoding="utf-8"))
    post = (WEATHER / "post.txt").read_text(encoding="utf-8").strip()
    prompt = (WEATHER / "image-prompt.txt").read_text(encoding="utf-8").strip()
    if not metadata.get("days") or not post or not prompt:
        raise RuntimeError("weather/ 內缺少完整的本週天氣輸出")
    return metadata, post, prompt


def weather_threads(metadata: dict) -> str:
    days = metadata["days"]
    start, end = days[0]["time"].replace("-", "/")[5:], days[-1]["time"].replace("-", "/")[5:]
    rainy = max(days, key=lambda item: item["precipitation_probability_max"])
    hot = max(days, key=lambda item: item["apparent_temperature_max"])
    return (
        f"🌦️ 沖繩 {start}～{end} 天氣速報｜最高體感約 {round(hot['apparent_temperature_max'])}°C，"
        f"最高降雨機率 {round(rainy['precipitation_probability_max'])}%。"
        "防曬、補水和折傘都別忘了；海上行程請看當日業者公告。"
        "\n👉 facebook.com/groups/okiplayground"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually update the one verified Sheet row")
    args = parser.parse_args()
    metadata, post, prompt = load_generated()
    target_date = metadata["days"][0]["time"].replace("-", "/")
    ws = worksheet()
    rows = ws.get_all_values()
    headers = rows[0]
    required = {"日期", "平台", "車款/主題", "帖文類型", "IG/FB文案", "Threads文案", "Hashtags", "發佈狀態"}
    missing = required - set(headers)
    if missing:
        raise RuntimeError(f"Sheet 缺少必要欄位：{', '.join(sorted(missing))}")
    index = {name: headers.index(name) for name in headers}
    matches = []
    for row_number, row in enumerate(rows[1:], start=2):
        value = lambda column: row[index[column]].strip() if index[column] < len(row) else ""
        is_weather = "天氣" in value("車款/主題") or "天氣" in value("帖文類型")
        if value("日期") == target_date and value("平台") == "OKIP" and is_weather:
            matches.append(row_number)
    if len(matches) != 1:
        raise RuntimeError(f"預期 {target_date} 只有一筆 OKIP 天氣列，實際找到 {len(matches)} 筆：{matches}")
    row_number = matches[0]
    hashtags = " ".join(part for part in post.splitlines() if part.startswith("#"))
    updates = {
        "IG/FB文案": post,
        "Threads文案": weather_threads(metadata),
        "Hashtags": hashtags,
        "發佈狀態": "AI初稿",
    }
    if "媒體建議" in index:
        updates["媒體建議"] = "附既有 7 天天氣範例圖，並使用首頁的 ChatGPT 圖片 Prompt 生成；資料來源：Open-Meteo 沖繩市日預報（含每日主導風向）。"
    if "備注" in index:
        updates["備注"] = "天氣文案由每週二排程更新；圖片請附範例圖後使用首頁 Prompt 生成。"
    print(f"目標 Sheet 第 {row_number} 列｜{target_date}｜OKIP 天氣速報")
    print("準備寫入欄位：" + "、".join(updates))
    if not args.apply:
        print("DRY RUN：未寫入。加上 --apply 才會更新。")
        return 0
    for column, value in updates.items():
        ws.update_cell(row_number, index[column] + 1, value)
    print("✅ 已將本週天氣帖文與圖片生成指引寫入 Sheet")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
