#!/usr/bin/env python3
"""Fetch latest AI hardware news via RSS, curate top 5, send to Feishu group."""

import urllib.request
import os
import urllib.error
import re
import json
from datetime import datetime
from html import unescape

def fetch_rss(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return ""

def parse_rss(xml):
    items = []
    # Handle both RSS 2.0 and Atom-like formats
    blocks = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    if not blocks:
        # Try Atom entry format
        blocks = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
    for block in blocks:
        title_m = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
        link_m = re.search(r'<link>(.*?)</link>', block)
        desc_m = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
        if not desc_m:
            desc_m = re.search(r'<summary[^>]*>(.*?)</summary>', block, re.DOTALL)
        if not desc_m:
            desc_m = re.search(r'<content[^>]*>(.*?)</content>', block, re.DOTALL)
        
        title = ''
        if title_m:
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            title = unescape(title)
        
        link = ''
        if link_m:
            link = link_m.group(1).strip()
        
        desc = ''
        if desc_m:
            desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
            desc = unescape(desc)
        
        if title and len(title) > 5:
            items.append({
                'title': title,
                'url': link,
                'snippet': desc[:300]
            })
    return items

# Hardware-related keywords
HARDWARE_KEYWORDS = [
    'chip', '芯片', 'robot', '硬件', 'hardware', 'device', 'device',
    'NVIDIA', 'AMD', 'Intel', 'processor', '处理器', 'sensor', '传感器',
    'semiconductor', '半导体', 'GPU', 'TPU', '算力', 'autonomous',
    'drone', '具身智能', 'embodied', '人形机器人', 'humanoid',
    'AI PC', 'datacenter', 'data center', 'server', '服务器',
    'robotics', '机器人', 'Tesla', 'Apple', 'Quantum', '量子',
    'memory', '内存', 'storage', '存储', 'edge computing', '边缘计算',
    'FPGA', 'ASIC', 'neuromorphic', 'brain-computer', '脑机',
    'wearable', '可穿戴', 'AR', 'VR', 'spatial', 'lidar', 'radar',
    'battery', '电池', 'EV', 'electric vehicle', 'automotive', '汽车',
    'manufacturing', '制造', '3D printing', '打印',
]

def is_hardware_related(item):
    text = (item['title'] + ' ' + item['snippet']).lower()
    for kw in HARDWARE_KEYWORDS:
        if kw.lower() in text:
            return True
    return False

# Step 1: Fetch RSS feeds
feeds = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("TechCrunch Robotics", "https://techcrunch.com/category/robotics/feed/"),
    ("Ars Technica", "https://arstechnica.com/feed/"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("The Verge AI", "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
]

print("=== Fetching RSS feeds ===")
all_news = []
for name, url in feeds:
    print(f"Fetching {name}...")
    xml = fetch_rss(url)
    if xml:
        items = parse_rss(xml)
        for item in items:
            item['source'] = name
            all_news.append(item)
        print(f"  Got {len(items)} items from {name}")
    else:
        print(f"  No data from {name}")

# Deduplicate
print(f"\nTotal raw items: {len(all_news)}")
seen = set()
unique = []
for n in all_news:
    key = n['title'][:60].lower()
    if key not in seen:
        seen.add(key)
        unique.append(n)

print(f"After dedup: {len(unique)} items")

# Step 2: Filter hardware-related
hardware_news = [n for n in unique if is_hardware_related(n)]
print(f"Hardware-related: {len(hardware_news)} items")

if len(hardware_news) >= 5:
    selected = hardware_news[:10]  # Take top 10 for curation
else:
    # Supplement with general AI news
    general_news = [n for n in unique if n not in hardware_news]
    needed = 5 - len(hardware_news)
    selected = hardware_news + general_news[:needed + 5]

print(f"Selected for curation: {len(selected)} items")

# Step 3: Pick Top 5 with priority scoring
def score_item(item):
    score = 0
    text = (item['title'] + ' ' + item['snippet']).lower()
    # Company mentions
    for brand in ['nvidia', 'amd', 'intel', 'apple', 'tesla', 'google', 'microsoft', 'openai', 'anthropic']:
        if brand in text:
            score += 3
    # Hardware keywords
    for kw in ['chip', '芯片', 'gpu', 'tpu', 'humanoid', '人形机器人', 'robot', '机器人', 'semiconductor', '半导体', 'processor', '处理器']:
        if kw.lower() in text:
            score += 2
    # Breaking news indicators
    for indicator in ['launch', 'announced', 'released', 'breakthrough', 'new', '首次', '发布', '推出']:
        if indicator.lower() in text:
            score += 1
    # Title length (longer titles tend to be more informative)
    score += len(item['title']) / 100
    return score

scored = [(score_item(n), n) for n in selected]
scored.sort(key=lambda x: -x[0])
top5 = [n for _, n in scored[:5]]

# Step 4: Format and send to Feishu
print("\n=== Top 5 AI Hardware News ===")
today = datetime.now().strftime('%Y-%m-%d')

lines = []
lines.append(f"🤖 AI硬件行业日报 | {today}")
lines.append("")

for i, item in enumerate(top5, 1):
    emoji = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣'][i-1]
    title = item['title']
    source = item['source']
    url = item['url']
    snippet = item['snippet']
    
    # Write a brief Chinese summary based on the English title/snippet
    summary = ""
    text_lower = (title + ' ' + snippet).lower()
    
    # Try to generate a meaningful one-line summary
    if 'nvidia' in text_lower:
        summary = f"英伟达动态：{title}"
    elif 'amd' in text_lower:
        summary = f"AMD动态：{title}"
    elif 'intel' in text_lower:
        summary = f"英特尔动态：{title}"
    elif 'humanoid' in text_lower or '人形' in text_lower or 'humanoid' in text_lower:
        summary = f"人形机器人进展：{title}"
    elif 'robot' in text_lower or '机器人' in text_lower:
        summary = f"机器人领域：{title}"
    elif 'chip' in text_lower or '芯片' in text_lower or 'semiconductor' in text_lower or '半导体' in text_lower:
        summary = f"芯片/半导体动态：{title}"
    elif 'gpu' in text_lower or 'tpu' in text_lower:
        summary = f"算力/GPU进展：{title}"
    elif 'tesla' in text_lower:
        summary = f"特斯拉动态：{title}"
    elif 'apple' in text_lower:
        summary = f"苹果动态：{title}"
    else:
        summary = f"{title}"
    
    lines.append(f"{emoji} {title}")
    lines.append(f"📌 {summary}")
    if url:
        lines.append(f"🔗 {url}")
    lines.append(f"📰 来源: {source}")
    lines.append("")

# Add insight
lines.append("💡 今日洞察：AI硬件领域持续加速，芯片算力竞赛与人形机器人产业化成为关注焦点。")

msg = "\n".join(lines)
print("\n" + msg)

# Send to Feishu
try:
    app_id = "cli_a97b1e4633f99cb0"
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = "oc_8b8978c0510660ec4da3c52ebc7bb9a3"
    
    # Get token
    auth_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    auth_req = urllib.request.Request(
        auth_url,
        json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"}
    )
    auth_resp = json.loads(urllib.request.urlopen(auth_req, timeout=10).read())
    token = auth_resp.get("tenant_access_token", "")
    
    if not token:
        print(f"Failed to get token: {auth_resp}")
    else:
        print(f"\nToken obtained: {token[:20]}...")
        
        # Send message
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
        body = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": msg})
        }
        send_req = urllib.request.Request(
            send_url,
            json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        )
        send_resp = json.loads(urllib.request.urlopen(send_req, timeout=10).read())
        print(f"发送结果: {json.dumps(send_resp, ensure_ascii=False, indent=2)}")
        
        if send_resp.get("code") == 0:
            print("✅ 消息发送成功！")
        else:
            print(f"❌ 发送失败: {send_resp}")

except Exception as e:
    print(f"Error sending to Feishu: {e}")
    import traceback
    traceback.print_exc()
