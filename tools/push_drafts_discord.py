#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Sheet 上「發佈狀態＝AI初稿」的帖文草稿推到 Discord #n-sona,每篇一則,方便手機逐篇審。

刻意跟 sona-sns-draft skill 解耦:只認 Sheet 上的「AI初稿」,所以就算起草 skill 被重寫,
這支照常運作。用本地 state 檔記錄推過的草稿(以 內容指紋 為 key),避免重推;
草稿被重寫(內容變了)會當成新的再推一次。

webhook 來源(依序):env DISCORD_WEBHOOK_SONA → ~/.config/sol/config.json 的 webhooks["n-sona"]。

用法:
  python3 tools/push_drafts_discord.py            # 推尚未推過的 AI初稿
  python3 tools/push_drafts_discord.py --dry-run  # 只印出會推什麼,不送、不記 state
  python3 tools/push_drafts_discord.py --force     # 忽略 state,全部重推
"""
import os, sys, json, time, hashlib, argparse, warnings
import urllib.request, urllib.error

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_draft_io as sd  # 沿用它的 _ws()（同一份憑證/Sheet）

STATE_PATH = os.path.expanduser("~/.config/sonasns/draft_push_state.json")
SOL_CONFIG = os.path.expanduser("~/.config/sol/config.json")
DISCORD_MAX = 1900  # 單則安全上限(Discord 硬上限 2000)


def webhook_url():
    url = os.environ.get("DISCORD_WEBHOOK_SONA")
    if url:
        return url
    if os.path.exists(SOL_CONFIG):
        with open(SOL_CONFIG, encoding="utf-8") as f:
            return json.load(f).get("webhooks", {}).get("n-sona")
    return None


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                return set(json.load(f).get("pushed", []))
        except Exception:
            return set()
    return set()


def save_state(pushed):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"pushed": sorted(pushed)}, f, ensure_ascii=False, indent=2)


def fingerprint(rec):
    # 內容變了就重推:key 綁 日期+平台+主題+兩個文案
    raw = "|".join([rec.get(k, "") for k in ("日期", "平台", "車款/主題", "IG/FB文案", "Threads文案")])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def build_message(rec):
    title = rec.get("車款/主題") or "(未命名主題)"
    head = f"📝 **SonaSNS 草稿待審** · {title}"
    meta = " · ".join(x for x in [rec.get("日期", ""), rec.get("星期", ""), rec.get("平台", "")] if x)
    parts = [head, meta, "━━━━━━━━━━"]
    if rec.get("IG/FB文案"):
        parts += ["📸 **IG/FB**", rec["IG/FB文案"]]
    if rec.get("Threads文案"):
        parts += ["", "🧵 **Threads**", rec["Threads文案"]]
    if rec.get("Hashtags"):
        parts += ["", "#️⃣ " + rec["Hashtags"]]
    if rec.get("媒體建議"):
        parts += ["", "🎬 媒體建議:" + rec["媒體建議"]]
    parts += ["━━━━━━━━━━", "✅ 審完到 Sheet 改「發佈狀態」"]
    return "\n".join(parts)


def chunk(text, size=DISCORD_MAX):
    if len(text) <= size:
        return [text]
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > size:
            if cur:
                out.append(cur)
            # 單行就超長就硬切
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


def collect_drafts():
    ws = sd._ws()
    rows = ws.get_all_values()
    hdr = rows[0]
    idx = {name: i for i, name in enumerate(hdr)}
    si = idx.get("發佈狀態", -1)
    out = []
    for n, r in enumerate(rows[1:], start=2):
        g = lambda name: (r[idx[name]].strip() if name in idx and idx[name] < len(r) else "")
        if si < 0 or (r[si].strip() if si < len(r) else "") != "AI初稿":
            continue
        rec = {k: g(k) for k in ("日期", "星期", "平台", "車款/主題",
                                 "IG/FB文案", "Threads文案", "Hashtags", "媒體建議")}
        rec["_row"] = n
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    url = webhook_url()
    if not a.dry_run and (not url or not url.startswith("https")):
        sys.exit("❌ 找不到 #n-sona webhook(env DISCORD_WEBHOOK_SONA 或 ~/.config/sol/config.json)")

    drafts = collect_drafts()
    state = set() if a.force else load_state()
    pending = [d for d in drafts if a.force or fingerprint(d) not in state]

    print(f"AI初稿 共 {len(drafts)} 篇,待推 {len(pending)} 篇" + ("(dry-run)" if a.dry_run else ""))
    if not pending:
        return

    pushed_now = 0
    for d in pending:
        msg = build_message(d)
        if a.dry_run:
            print("\n" + "=" * 40 + f"  row {d['_row']}\n" + msg)
            continue
        try:
            for i, ch in enumerate(chunk(msg)):
                post(url, ch)
                time.sleep(0.4)  # 避免 Discord rate limit
            state.add(fingerprint(d))
            pushed_now += 1
            print(f"✅ row {d['_row']} 已推 · {d.get('車款/主題','')[:20]}")
        except urllib.error.HTTPError as e:
            print(f"⚠️ row {d['_row']} 推送失敗 {e.code}: {e.read().decode()[:120]}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ row {d['_row']} 推送失敗: {e}", file=sys.stderr)

    if not a.dry_run and pushed_now:
        save_state(state)
        print(f"— 本次推 {pushed_now} 篇,state 已更新")


if __name__ == "__main__":
    main()
