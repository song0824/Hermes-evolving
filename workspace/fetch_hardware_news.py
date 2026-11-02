#!/usr/bin/env python3
"""Fetch RSS, filter hardware news, output top items."""
import urllib.request, re, json
from html import unescape

def fetch_rss(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.read().decode('utf-8', errors='replace')
    except:
        return ""

def parse_rss(xml):
    items = []
    blocks = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    for block in blocks:
        title_m = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
        link_m = re.search(r'<link>(.*?)</link>', block)
        desc_m = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ''
        title = unescape(title)
        link = link_m.group(1).strip() if link_m else ''
        desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ''
        desc = unescape(desc)
        if title and len(title) > 5:
            items.append({'title': title, 'url': link, 'snippet': desc[:300]})
    return items

HARDWARE_KEYWORDS = [
    'chip', '芯片', 'robot', '硬件', 'hardware', 'device',
    'NVIDIA', 'AMD', 'Intel', 'processor', '传感器',
    'semiconductor', '半导体', 'GPU', 'TPU', '算力', 'autonomous',
    'drone', '具身智能', 'embodied', 'humanoid', '机器人',
    'AI PC', 'datacenter', 'server', '服务器', 'robotics',
    'Tesla', 'Quantum', '量子', 'memory', '内存', 'storage', '存储',
    'edge computing', '边缘计算', 'FPGA', 'ASIC', 'neuromorphic',
    '脑机', 'wearable', '可穿戴', 'AR', 'VR', 'lidar', 'radar',
    'battery', '电池', 'EV', 'electric vehicle', 'automotive', '汽车',
    'manufacturing', '制造', '3D printing', '打印',
]

def is_hardware(item):
    text = (item['title'] + ' ' + item.get('snippet','')).lower()
    for kw in HARDWARE_KEYWORDS:
        if kw.lower() in text:
            return True
    return False

def hw_score(n):
    s = 0
    t = (n['title'] + ' ' + n.get('snippet','')).lower()
    for kw in ['nvidia','amd','intel','gpu','tpu','chip','芯片','semiconductor','半导体',
               'humanoid','人形','robot','机器人','processor','处理器','hardware','硬件',
               'sensor','传感器','datacenter','data center','server','服务器']:
        if kw in t: s += 2
    for kw in ['launch','announce','release','breakthrough','首次','发布','推出','unveil']:
        if kw in t: s += 1
    return s

feeds = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("TechCrunch Robotics", "https://techcrunch.com/category/robotics/feed/"),
    ("Ars Technica", "https://arstechnica.com/feed/"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
]

all_news = []
for name, url in feeds:
    xml = fetch_rss(url)
    if xml:
        for item in parse_rss(xml):
            item['source'] = name
            all_news.append(item)

seen = set()
unique = []
for n in all_news:
    key = n['title'][:60].lower()
    if key not in seen:
        seen.add(key)
        unique.append(n)

hardware = [n for n in unique if is_hardware(n)]
hardware.sort(key=lambda x: -hw_score(x))

for i, n in enumerate(hardware[:10]):
    print(f"[{i+1}] {n['title']}")
    print(f"    Source: {n['source']}")
    print(f"    URL: {n['url']}")
    print(f"    Snippet: {n.get('snippet','')[:150]}")
    print(f"    Score: {hw_score(n)}")
    print()
