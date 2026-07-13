#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把最新一份 Sona 週報(reports/weekly/sona_weekly_YYYY-MM-DD.md)推到 Discord #n-sona。

刻意跟 sona-radar-weekly-report skill 解耦:只認 reports/weekly/ 下的 md 檔,
所以就算週報 skill 被重寫,這支照常運作。用本地 state 記錄推過的檔名,避免重推
(同一份週報內容變了會重推)。

webhook 來源(依序):env DISCORD_WEBHOOK_SONA → ~/.config/sol/config.json 的 webhooks["n-sona"]。

用法:
  python3 tools/push_weekly_discord.py            # 推最新且尚未推過的週報
  python3 tools/push_weekly_discord.py --dry-run  # 只印,不送、不記 state
  python3 tools/push_weekly_discord.py --force     # 忽略 state,重推最新一份
"""
import os, sys, glob, json, time, hashlib, argparse
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
WEEKLY_DIR = os.path.join(HERE, "..", "reports", "weekly")
STATE_PATH = os.path.expanduser("~/.config/sonasns/weekly_push_state.json")
SOL_CONFIG = os.path.expanduser("~/.config/sol/config.json")
DISCORD_MAX = 1900


def webhook_url():
    url = os.environ.get("DISCORD_WEBHOOK_SONA")
    if url:
        return url
    if os.path.exists(SOL_CONFIG):
        with open(SOL_CONFIG, encoding="utf-8") as f:
            return json.load(f).get("webhooks", {}).get("n-sona")
    return None


def latest_report():
    files = sorted(glob.glob(os.path.join(WEEKLY_DIR, "sona_weekly_*.md")))
    return files[-1] if files else None


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                return json.load(f).get("pushed", {})
        except Exception:
            return {}
    return {}


def save_state(pushed):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"pushed": pushed}, f, ensure_ascii=False, indent=2)


def chunk(text, size=DISCORD_MAX):
    if len(text) <= size:
        return [text]
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > size:
            if cur:
                out.append(cur)
            while len(line) > size:
                out.append(line[:size]); line = line[size:]
            cur = line
        else:
            cur = cur + "\n" + line if cur else line
    if cur:
        out.append(cur)
    return out


def post(url, content):
    data = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "User-Agent": "SolBot (https://suniverse.local, 0.1)",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    rpt = latest_report()
    if not rpt:
        print("(reports/weekly/ 下沒有週報,略過)")
        return
    name = os.path.basename(rpt)
    body = open(rpt, encoding="utf-8").read().strip()
    digest = hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]

    state = {} if a.force else load_state()
    if not a.force and state.get(name) == digest:
        print(f"(最新週報 {name} 已推過,略過)")
        return

    header = f"📊 **{name.replace('.md','').replace('sona_weekly_','Sona 週報 ')}** — 已更新到 #n-sona"
    msg = header + "\n\n" + body

    if a.dry_run:
        print(f"[dry-run] 會推 {name}:\n" + "-" * 40)
        print(msg[:1500] + ("\n…(略)" if len(msg) > 1500 else ""))
        return

    url = webhook_url()
    if not url or not url.startswith("https"):
        sys.exit("❌ 找不到 #n-sona webhook(env DISCORD_WEBHOOK_SONA 或 ~/.config/sol/config.json)")

    try:
        for ch in chunk(msg):
            post(url, ch)
            time.sleep(0.4)
        state[name] = digest
        save_state(state)
        print(f"✅ 已推週報 {name} 到 #n-sona")
    except urllib.error.HTTPError as e:
        sys.exit(f"⚠️ 推送失敗 {e.code}: {e.read().decode()[:150]}")


if __name__ == "__main__":
    main()
