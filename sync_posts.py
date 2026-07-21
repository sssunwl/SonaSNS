#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SonaSNS 自動同步腳本
每天定時檢查 Google Sheet 並同步到 GitHub Pages
"""

import gspread
import re
import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

def get_service_account_info():
    """從環境變數中讀取 Service Account 憑證"""
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')

    if creds_json:
        return json.loads(creds_json)

    # Local verification uses the same credential location as the drafting tool.
    local_creds = Path.home() / '.config' / 'sonasns' / 'credentials.json'
    if local_creds.exists():
        return json.loads(local_creds.read_text(encoding='utf-8'))

    print("❌ 缺少 GOOGLE_SERVICE_ACCOUNT_JSON 認證信息")
    sys.exit(1)


def get_weather_prompt():
    """Return the current weekly weather prompt and the Wednesday it belongs to."""
    prompt_path = Path('weather/image-prompt.txt')
    data_path = Path('weather/weather.json')
    if not prompt_path.exists() or not data_path.exists():
        return None, None
    try:
        days = json.loads(data_path.read_text(encoding='utf-8')).get('days', [])
        if not days:
            return None, None
        prompt = prompt_path.read_text(encoding='utf-8').strip()
        return prompt, days[0]['time'].replace('-', '/')
    except (OSError, ValueError, KeyError) as exc:
        print(f"⚠️ 無法讀取天氣 Prompt，略過嵌入：{exc}")
        return None, None

def get_posts_from_sheet():
    """從 Google Sheet 讀取帖文"""
    service_account_info = get_service_account_info()

    gc = gspread.service_account_from_dict(service_account_info)

    sheet = gc.open_by_key('1gTbG5il6CtomkTfRXmFXwx7_4AIG8CjOnfsdoRynuS4')
    worksheet = sheet.sheet1

    all_data = worksheet.get_all_values()
    headers = all_data[0]

    date_idx = headers.index('日期')
    weekday_idx = headers.index('星期')
    platform_idx = headers.index('平台')
    topic_idx = headers.index('車款/主題')
    type_idx = headers.index('帖文類型')
    published_idx = headers.index('發佈版本')
    ig_fb_idx = headers.index('IG/FB文案')
    hashtags_idx = headers.index('Hashtags')
    youtube_idx = headers.index('YouTube連結')
    status_idx = headers.index('發佈狀態')
    threads_idx = headers.index('Threads文案') if 'Threads文案' in headers else -1

    # Keep the current calendar useful without hard-coding specific months.
    today = datetime.now().date()
    earliest, latest = today - timedelta(days=45), today + timedelta(days=120)
    weather_prompt, weather_date = get_weather_prompt()
    posts = []
    for row in all_data[1:]:
        if not row or not row[0]:
            continue

        date = row[date_idx].strip()
        try:
            post_date = datetime.strptime(date, '%Y/%m/%d').date()
        except ValueError:
            continue
        if earliest <= post_date <= latest:
            # 優先用發佈版本，沒有就用 IG/FB文案（純空白視同空，避免誤按空格蓋掉草稿）
            content = row[published_idx] if published_idx < len(row) else ''
            if not content.strip() and ig_fb_idx < len(row):
                content = row[ig_fb_idx]

            topic = (row[topic_idx] if topic_idx < len(row) else '').replace('\n', ' ').replace('\r', ' ').strip()

            if content or topic:
                post = {
                    'date': date,
                    'weekday': row[weekday_idx],
                    'platform': row[platform_idx],
                    'topic': topic,
                    'type': row[type_idx],
                    'content': content,
                    'hashtags': (row[hashtags_idx].split() if hashtags_idx < len(row) else []),
                    'mediaLink': (row[youtube_idx] if youtube_idx < len(row) and row[youtube_idx].startswith('http') else None),
                    'status': (row[status_idx] if status_idx < len(row) else '待起稿'),
                    'threads': (row[threads_idx].strip() if 0 <= threads_idx < len(row) else '')
                }
                # Only the matching Wednesday OKIP weather post gets this week's prompt.
                if (weather_prompt and date == weather_date and post['platform'] == 'OKIP'
                        and ('天氣' in post['type'] or '天氣' in post['topic'] or '天氣' in post['content'])):
                    post['imagePrompt'] = weather_prompt
                posts.append(post)

    return posts

def generate_posts_js(posts):
    """生成 JavaScript posts 陣列"""
    js_code = "const posts = [\n"
    for i, post in enumerate(posts):
        content = post['content'].replace('\\', '\\\\').replace('`', '\\`')
        threads = post.get('threads', '').replace('\\', '\\\\').replace('`', '\\`')
        image_prompt = post.get('imagePrompt', '').replace('\\', '\\\\').replace('`', '\\`')
        hashtags_str = ', '.join([f"'{h}'" for h in post['hashtags']])
        media = f"'{post['mediaLink']}'" if post['mediaLink'] else "null"
        comma = "," if i < len(posts) - 1 else ""

        topic = post['topic'].replace("'", "\\'")

        js_code += f"""            {{
                date: '{post['date']}',
                weekday: '{post['weekday']}',
                platform: '{post['platform']}',
                topic: '{topic}',
                type: '{post['type']}',
                content: `{content}`,
                threads: `{threads}`,
                imagePrompt: `{image_prompt}`,
                hashtags: [{hashtags_str}],
                mediaLink: {media},
                status: '{post['status']}'
            }}{comma}
"""

    js_code += "        ];"
    return js_code

def update_index_html(js_code):
    """更新 index.html 中的 posts 陣列"""
    with open('index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    pattern = r'const posts = \[.*?\];'
    updated_html = re.sub(pattern, js_code, html, flags=re.DOTALL)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(updated_html)

    return updated_html != html  # 返回是否有更改

def main():
    print("🔄 開始同步帖文...")
    print(f"⏰ 時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        posts = get_posts_from_sheet()
        print(f"✅ 從 Sheet 讀取 {len(posts)} 條帖文")

        js_code = generate_posts_js(posts)
        print(f"✅ 已生成 JavaScript 代碼")

        changed = update_index_html(js_code)

        try:  # 鏡射到 Discord #n-sona(失敗不影響同步)
            from _discord import notify_discord
            notify_discord(
                f"🔄 SonaSNS 同步完成:{len(posts)} 條帖文"
                + ("(index.html 已更新)" if changed else "(無新更改)")
            )
        except Exception:
            pass

        if changed:
            print("✅ index.html 已更新")
            return 0
        else:
            print("ℹ️ 沒有新的更改")
            return 0

    except Exception as e:
        print(f"❌ 同步失敗：{e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
