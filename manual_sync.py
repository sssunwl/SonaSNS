#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SonaSNS 手動同步腳本
從 CSV 檔案同步帖文到 index.html（無需 Google 認證）
"""

import csv
import re
import sys

def read_posts_from_csv(csv_file):
    """從 CSV 檔案讀取帖文"""
    posts = []

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                date = row.get('日期', '').strip()

                # 只讀取 6 月和 7 月資料
                if date.startswith('2026/06/') or date.startswith('2026/07/'):
                    # 優先用發佈版本，沒有就用 IG/FB文案
                    content = row.get('發佈版本', '').strip()
                    if not content:
                        content = row.get('IG/FB文案', '').strip()

                    if content:
                        topic = row.get('車款/主題', '').replace('\n', ' ').replace('\r', ' ').strip()
                        hashtags_str = row.get('Hashtags', '').strip()
                        hashtags = hashtags_str.split() if hashtags_str else []
                        youtube_link = row.get('YouTube連結', '').strip()
                        youtube_link = youtube_link if youtube_link.startswith('http') else None

                        post = {
                            'date': date,
                            'weekday': row.get('星期', '').strip(),
                            'platform': row.get('平台', '').strip(),
                            'topic': topic,
                            'type': row.get('帖文類型', '').strip(),
                            'content': content,
                            'hashtags': hashtags,
                            'mediaLink': youtube_link,
                            'status': row.get('發佈狀態', '').strip()
                        }
                        posts.append(post)

    except FileNotFoundError:
        print(f"❌ 找不到檔案：{csv_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 讀取 CSV 出錯：{e}")
        sys.exit(1)

    return posts

def generate_posts_js(posts):
    """生成 JavaScript posts 陣列"""
    js_code = "const posts = [\n"
    for i, post in enumerate(posts):
        content = post['content'].replace('\\', '\\\\').replace('`', '\\`')
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
                hashtags: [{hashtags_str}],
                mediaLink: {media},
                status: '{post['status']}'
            }}{comma}
"""

    js_code += "        ];"
    return js_code

def update_index_html(js_code):
    """更新 index.html 中的 posts 陣列"""
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()

        pattern = r'const posts = \[.*?\];'
        updated_html = re.sub(pattern, js_code, html, flags=re.DOTALL)

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(updated_html)

        return updated_html != html

    except Exception as e:
        print(f"❌ 更新 index.html 出錯：{e}")
        sys.exit(1)

def main():
    print("🔄 開始手動同步...")

    # 用戶從 Google Sheet 導出 CSV，預設檔名為 SonaSNS.csv
    csv_file = 'SonaSNS.csv'

    if len(sys.argv) > 1:
        csv_file = sys.argv[1]

    posts = read_posts_from_csv(csv_file)
    print(f"✅ 從 CSV 讀取 {len(posts)} 條帖文")

    js_code = generate_posts_js(posts)
    print(f"✅ 已生成 JavaScript 代碼")

    changed = update_index_html(js_code)

    if changed:
        print("✅ index.html 已更新")
        print("\n📝 下一步：")
        print("   git add index.html")
        print("   git commit -m 'chore: manual sync posts from Google Sheet'")
        print("   git push origin main")
        return 0
    else:
        print("ℹ️ 沒有新的更改")
        return 1

if __name__ == '__main__':
    sys.exit(main())
