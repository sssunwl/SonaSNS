#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SonaSNS Sheet 起草 I/O 小工具 — 給每日排程的 AI 用。
把「決定內容(AI)」跟「寫進 Sheet(程式)」分開,並用白名單鎖死可寫欄位。

允許寫: IG/FB文案 / Threads文案 / Hashtags / 發佈狀態 / 備注 / 媒體建議 / 媒體路徑
禁止寫: 發佈版本(SS 專屬)/ 車款主題 / 日期 / 平台  ← 想寫也會被擋

用法:
  python3 tools/sheet_draft_io.py pending [--days 14]     # 列出待處理的行(JSON)
  python3 tools/sheet_draft_io.py write --row 42 --json '{"IG/FB文案":"...","發佈狀態":"AI初稿"}'
"""
import gspread, os, sys, json, argparse, warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

SHEET_ID = "1gTbG5il6CtomkTfRXmFXwx7_4AIG8CjOnfsdoRynuS4"
CREDS = os.path.expanduser("~/.config/sonasns/credentials.json")

ALLOWED = {"IG/FB文案", "Threads文案", "Hashtags", "發佈狀態", "備注", "媒體建議", "媒體路徑"}
FORBIDDEN = {"發佈版本", "車款/主題", "日期", "平台", "星期"}


def _ws():
    # GitHub Actions 用 env 憑證,本機用 ~/.config/sonasns/credentials.json
    env_creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_creds:
        gc = gspread.service_account_from_dict(json.loads(env_creds))
    else:
        gc = gspread.service_account(filename=CREDS)
    return gc.open_by_key(SHEET_ID).sheet1


def _hdr(ws):
    return ws.row_values(1)


def cmd_pending(days):
    ws = _ws()
    rows = ws.get_all_values()
    hdr = rows[0]
    def i(n): return hdr.index(n) if n in hdr else -1
    di, pi, ti, capi, suppi = i("日期"), i("平台"), i("車款/主題"), i("IG/FB文案"), i("帖文補充資料")
    today = datetime.now().strftime("%Y/%m/%d")
    limit = (datetime.now() + timedelta(days=days)).strftime("%Y/%m/%d")
    out = []
    for n, r in enumerate(rows[1:], start=2):   # sheet 實際行號(表頭在第 1 行)
        g = lambda idx: (r[idx] if 0 <= idx < len(r) else "").strip()
        d, plat, topic, cap = g(di), g(pi), g(ti), g(capi)
        if not d or d < today or d > limit:
            continue
        if plat in ("休", "", None):
            continue
        if topic and not cap:
            mode = "draft"          # 有主題無文案 → 寫草稿
        elif not topic:
            mode = "suggest"        # 無主題 → 建議主題 + 媒體
        else:
            continue                # 已有文案,跳過
        out.append({"row": n, "date": d, "platform": plat, "topic": topic,
                    "supp": g(suppi), "mode": mode})
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_write(row, payload):
    ws = _ws()
    hdr = _hdr(ws)
    try:
        fields = json.loads(payload)
    except Exception as e:
        print(f"❌ JSON 解析失敗: {e}"); sys.exit(1)
    wrote, blocked = [], []
    for col, val in fields.items():
        if col in FORBIDDEN or col not in ALLOWED:
            blocked.append(col); continue
        if col not in hdr:
            blocked.append(f"{col}(欄位不存在)"); continue
        ws.update_cell(row, hdr.index(col) + 1, val)
        wrote.append(col)
    print(f"✅ row {row} 已寫: {wrote}" + (f" | ⛔ 擋下: {blocked}" if blocked else ""))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("pending"); p1.add_argument("--days", type=int, default=14)
    p2 = sub.add_parser("write"); p2.add_argument("--row", type=int, required=True); p2.add_argument("--json", required=True)
    a = ap.parse_args()
    if a.cmd == "pending":
        cmd_pending(a.days)
    else:
        cmd_write(a.row, a.json)


if __name__ == "__main__":
    main()
