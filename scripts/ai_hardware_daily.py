#!/usr/bin/env python3
"""AI硬件行业日报 - 抓取RSS、筛选Top5、发送到飞书群"""

import urllib.request, re, json, yaml, os, ssl
from datetime import datetime

# ── RSS Fetching ──

def fetch_rss(url):
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*"
        })
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}")
        return ""

def parse_rss(xml):
    items = []
    blocks = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    for block in blocks:
        title_m = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
        link_m = re.search(r'<link>(.*?)</link>', block)
        desc_m = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
        pub_m = re.search(r'<pubDate>(.*?)</pubDate>', block)
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ''
        link = link_m.group(1).strip() if link_m else ''
        desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ''
        pubdate = pub_m.group(1).strip() if pub_m else ''
        if title and len(title) > 5:
            items.append({'title': title, 'url': link, 'snippet': desc[:300], 'pubdate': pubdate})
    return items

def parse_atom(xml):
    items = []
    entries = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
    for entry in entries:
        title_m = re.search(r'<title[^>]*>(.*?)</title>', entry, re.DOTALL)
        link_m = re.search(r'<link[^>]+href="([^"]+)"', entry)
        summary_m = re.search(r'<summary[^>]*>(.*?)</summary>', entry, re.DOTALL)
        content_m = re.search(r'<content[^>]*>(.*?)</content>', entry, re.DOTALL)
        pub_m = re.search(r'<published>(.*?)</published>', entry) or re.search(r'<updated>(.*?)</updated>', entry)
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ''
        link = link_m.group(1).strip() if link_m else ''
        desc = summary_m or content_m
        desc_text = re.sub(r'<[^>]+>', '', desc.group(1)).strip() if desc else ''
        pubdate = pub_m.group(1).strip() if pub_m else ''
        if title and len(title) > 5:
            items.append({'title': title, 'url': link, 'snippet': desc_text[:300], 'pubdate': pubdate})
    return items

# ── Hardware Keywords ──
HW_KEYWORDS = [
    'chip', '芯片', 'robot', '机器人', 'hardware', '硬件', 'device', '设备',
    'NVIDIA', 'AMD', 'Intel', 'processor', '处理器', 'sensor', '传感器',
    'semiconductor', '半导体', 'GPU', 'TPU', '算力', 'autonomous',
    'drone', '无人机', '具身智能', 'embodied', '人形机器人', 'humanoid',
    'AI PC', 'datacenter', 'server', '服务器', 'memory', '存储',
    'manufacturing', '制造', 'edge', '边缘', 'IoT', '物联网',
    'battery', '电池', 'EV', 'electric vehicle', '电动车',
    'quantum', '量子', 'neuromorphic', '类脑', 'optical', '光芯片',
    'RISC-V', 'ARM', 'foundry', '代工', 'lithography', '光刻',
    'wearable', '可穿戴', 'AR', 'VR', 'smart glasses', '智能眼镜',
    'silicon', '硅', 'wafer', '晶圆', 'packaging', '封装',
    'autonomous driving', '自动驾驶', 'smart car', '智能汽车',
]

def is_hardware_related(item):
    text = (item['title'] + ' ' + item.get('snippet', '')).lower()
    for kw in HW_KEYWORDS:
        if kw.lower() in text:
            return True
    return False

# ── Score News ──
def score_item(item):
    score = 0
    text = (item['title'] + ' ' + item.get('snippet', '')).lower()
    # Company keywords
    for company in ['nvidia', 'amd', 'intel', 'apple', 'google', 'microsoft', 'tesla', 'openai', 'anthropic', 'meta', 'amazon', 'huawei', '华为', '小米', '字节跳动']:
        if company in text:
            score += 3
    # Hardware keywords count
    for kw in HW_KEYWORDS:
        if kw.lower() in text:
            score += 2
    return score

# ── Main ──
feeds = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("TechCrunch Robotics", "https://techcrunch.com/category/robotics/feed/"),
    ("Ars Technica", "https://arstechnica.com/feed/"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

print("=" * 60)
print(f"AI硬件行业日报 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 60)

all_news = []
for name, url in feeds:
    print(f"\n📡 Fetching: {name} ...")
    xml = fetch_rss(url)
    if not xml:
        continue
    # Try RSS first, fall back to Atom
    if '<item>' in xml:
        items = parse_rss(xml)
    elif '<entry>' in xml:
        items = parse_atom(xml)
    else:
        items = []
    print(f"  → {len(items)} items")
    for item in items:
        item['source'] = name
        all_news.append(item)

print(f"\n📊 Total raw items: {len(all_news)}")

# Deduplicate
seen = set()
unique = []
for n in all_news:
    key = n['title'][:60].lower()
    if key not in seen:
        seen.add(key)
        unique.append(n)

print(f"   After dedup: {len(unique)}")

# Filter hardware-related
hw_news = [n for n in unique if is_hardware_related(n)]
print(f"   Hardware-related: {len(hw_news)}")

# If not enough hardware news, supplement with general AI news
if len(hw_news) < 5:
    general = [n for n in unique if not is_hardware_related(n)]
    general.sort(key=lambda x: score_item(x), reverse=True)
    hw_news.extend(general[:5 - len(hw_news)])
    print(f"   Supplemented with general AI: {len(hw_news)} total")

# Score and sort
hw_news.sort(key=lambda x: score_item(x), reverse=True)
top5 = hw_news[:5]

print(f"\n🏆 Top 5:")
for i, item in enumerate(top5, 1):
    print(f"  {i}. [{item['source']}] {item['title'][:80]}")

# ── Write summaries (manual curation based on content) ──
summaries = []
for item in top5:
    summaries.append({
        'title': item['title'],
        'url': item['url'],
        'source': item['source'],
        'snippet': item.get('snippet', '')[:200],
    })

# ── Send to Feishu ──
with open('/root/.hermes/config.yaml') as f:
    config = yaml.safe_load(f)

# Try both config structures
feishu_config = config.get('feishu', config.get('platforms', {}).get('feishu', {}))
extra = feishu_config.get('extra', feishu_config)
app_id = extra.get('app_id')
app_secret = extra.get('app_secret')

if not app_id or not app_secret:
    print("\n❌ Feishu credentials not found in config")
    # Just print the report
else:
    # Get token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    req = urllib.request.Request(url, json.dumps({
        "app_id": app_id,
        "app_secret": app_secret
    }).encode(), headers={"Content-Type": "application/json"})
    
    ctx = ssl.create_default_context()
    resp_data = json.loads(urllib.request.urlopen(req, context=ctx).read())
    token = resp_data.get("tenant_access_token")
    print(f"\n🔑 Token obtained: {token[:20]}...")

    today = datetime.now().strftime('%Y-%m-%d')
    
    # Build message
    lines = [f"AI硬件行业日报 | {today}", ""]
    
    for i, s in enumerate(summaries, 1):
        # Truncate long titles
        title = s['title']
        if len(title) > 120:
            title = title[:117] + "..."
        lines.append(f"{i}. {title}")
        # Add snippet if available
        if s['snippet']:
            snippet = s['snippet'][:150]
            if len(s['snippet']) > 150:
                snippet += "..."
            lines.append(f"   {snippet}")
        lines.append(f"   来源: {s['source']} | {s['url']}")
        lines.append("")
    
    lines.append("---")
    
    # Add a summary insight
    keywords_found = set()
    for s in summaries:
        text = (s['title'] + ' ' + s.get('snippet', '')).lower()
        for kw in ['nvidia', 'gpu', '芯片', 'robot', '机器人', 'humanoid', 'semiconductor', 'AI PC', 'datacenter', '自动驾驶', 'smart glasses', 'AR', 'VR', '电池', 'EV', '量子']:
            if kw.lower() in text:
                keywords_found.add(kw)
    
    insight_parts = list(keywords_found)[:3]
    if insight_parts:
        insight = f"今日热点关键词: {', '.join(insight_parts)}"
    else:
        insight = "今日涵盖芯片、机器人、AI基础设施等多个硬件方向"
    lines.append(insight)
    
    msg = "\n".join(lines)
    print(f"\n📝 Message length: {len(msg)} chars")
    print(f"📝 Message preview:\n{msg[:300]}...")

    # Send
    send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    body = {
        "receive_id": "oc_8b8978c0510660ec4da3c52ebc7bb9a3",
        "msg_type": "text",
        "content": json.dumps({"text": msg})
    }
    req = urllib.request.Request(send_url, json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    
    try:
        resp = json.loads(urllib.request.urlopen(req, context=ctx).read())
        print(f"\n📤 Send result: {json.dumps(resp, ensure_ascii=False)}")
    except Exception as e:
        print(f"\n❌ Send failed: {e}")

# ── Output final report ──
print("\n" + "=" * 60)
print("FINAL REPORT")
print("=" * 60)

today = datetime.now().strftime('%Y-%m-%d')
report_lines = [f"AI硬件行业日报 | {today}", ""]

for i, s in enumerate(summaries, 1):
    title = s['title']
    if len(title) > 120:
        title = title[:117] + "..."
    report_lines.append(f"{i}. {title}")
    if s['snippet']:
        snippet = s['snippet'][:150]
        if len(s['snippet']) > 150:
            snippet += "..."
        report_lines.append(f"   {snippet}")
    report_lines.append(f"   来源: {s['source']} | {s['url']}")
    report_lines.append("")

report_lines.append("---")

keywords_found = set()
for s in summaries:
    text = (s['title'] + ' ' + s.get('snippet', '')).lower()
    for kw in ['nvidia', 'gpu', '芯片', 'robot', '机器人', 'humanoid', 'semiconductor', 'AI PC', 'datacenter', '自动驾驶', 'smart glasses', 'AR', 'VR', '电池', 'EV', '量子']:
        if kw.lower() in text:
            keywords_found.add(kw)

insight_parts = list(keywords_found)[:3]
if insight_parts:
    insight = f"今日热点关键词: {', '.join(insight_parts)}"
else:
    insight = "今日涵盖芯片、机器人、AI基础设施等多个硬件方向"
report_lines.append(insight)

print("\n".join(report_lines))
