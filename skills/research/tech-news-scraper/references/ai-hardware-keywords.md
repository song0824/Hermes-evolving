# AI Hardware News Digest — Keyword Reference

## Hardware Keywords for Filtering

Use these keywords to filter a broad RSS article pool for AI hardware-related news:

```python
HARDWARE_KEYWORDS = [
    'chip', '芯片', 'nvidia', 'amd', 'intel', 'gpu', 'tpu', 'processor', '处理器',
    'semiconductor', '半导体', 'sensor', '传感器', 'memory', '内存', 'storage', '存储',
    'humanoid', '人形机器人', 'robot', '机器人', 'robotics', 'autonomous',
    'embodied', '具身智能', 'drone', 'datacenter', 'data center', 'server', '服务器',
    'quantum', '量子', 'fpga', 'asic', 'neuromorphic', '脑机',
    'ai pc', 'edge computing', '边缘计算',
    'lidar', 'radar', 'battery', '电池', 'electric vehicle', 'automotive',  # NOTE: removed 'ev' — 2-letter keyword causes false positives
    'wearable', '可穿戴',  # NOTE: removed 'ar', 'vr' — 2-letter keywords cause massive false positives (hear, start, card, etc.)
    'virtual reality', 'xr', 'spatial',  # Use full terms instead of 'ar'/'vr'
    '3d printing', '打印', 'manufacturing', '制造', 'factory',
    'satellite', '卫星', 'space datacenter', 'orbital', 'orbit',
    'smart glasses', 'accelerator', 'neocloud', 'smartphone',
    'exoskeleton', '外骨骼', 'compute', '算力', 'llm serving', 'hbf',
    'silicon', 'wafer', 'foundry', 'packaging', 'cfet', 'angstrom',
    'nvm', 'non-volatile', 'edge ai', 'on-device', 'ondevice', 'inference',
    'billion', 'funding', 'raise', 'acquisition', 'ipo',
    # Emerging categories (2026-10 verified):
    'physical ai', 'cosmos', 'isaac', 'jetson', 'nim',  # Nvidia Physical AI stack
    'smart ring', 'wearable ai', 'local-first', 'local first', 'meeting note',  # Edge/wearable AI
]

def is_hardware(item):
    text = (item['title'] + ' ' + item.get('snippet', '')).lower()
    return any(kw.lower() in text for kw in HARDWARE_KEYWORDS)
```

⚠️ **Short keyword false positive pitfall**: 2-3 letter keywords like `'ar'`, `'edge'`, `'car'` cause massive false positives (e.g., "he**ar**", "st**ar**t", "advan**car**", "**car**d", "**edge** case"). Avoid adding such short keywords to the filter list, or use word-boundary matching (`re.search(r'\b' + kw + r'\b', text)`) for short terms. In practice, it's better to remove `'ar'` and `'car'` from the keyword list entirely and rely on longer terms like `'data center'`, `'robotics'`, etc. If you need short keywords, always verify matches against the title (not just the snippet).

## Noise Filter for Event/Promo Content

```python
NOISE_KEYWORDS = [
    'disrupt ', 'battlefield', 'ticket', 'early bird', 'save up',
    'applications close', 'apply to speak', 'exhibit at',
    'last day', 'days left', 'weeks left', 'apply before',
    'lock in', 'get in front of', 'second pass',
    'final 24 hours', 'two weeks left', '5 days left',
    '2 days left', '3 days', 'startup battlefield',
    'register now', 'register by', 'save up to', 'register to save',
    'expo+', 'expo pass', 'breakout session', 'roundtable',
    'full agenda', 'session agenda', 'hands-on:',
    'grab your', 'your final chance', 'book by',
    'reason to attend', 'momentum', '50% off',
]

def is_noise(title):
    tl = title.lower()
    return any(kw in tl for kw in NOISE_KEYWORDS)
```

## Scoring for Ranking Hardware Articles

### Simple two-tier scoring (recommended)
```python
def hw_score(n):
    s = 0
    t = (n['title'] + ' ' + n.get('snippet', '')).lower()
    # Strong hardware signals (weight 2)
    for kw in ['nvidia', 'amd', 'intel', 'gpu', 'tpu', 'chip', '芯片',
               'semiconductor', '半导体', 'humanoid', '人形', 'robot', '机器人',
               'processor', '处理器', 'hardware', '硬件', 'sensor', '传感器',
               'datacenter', 'data center', 'server', '服务器']:
        if kw in t:
            s += 2
    # Breaking news indicators (weight 1)
    for kw in ['launch', 'announce', 'release', 'breakthrough',
               '首次', '发布', '推出', 'unveil']:
        if kw in t:
            s += 1
    return s
```

### Enhanced weighted scoring (for large article pools, 50+)
When dealing with 50+ articles across many sources, use a weighted approach where specific company/technology terms get higher scores:
```python
HIGH_IMPACT_KW = [
    'nvidia', 'amd', 'intel', 'tsmc', 'samsung', 'asml',
    'hbm', 'gpu', 'semiconductor', '芯片', '半导体',
    'humanoid', '人形机器人', 'data center', 'datacenter',
    'ai chip', 'ai hardware', 'exoskeleton', 'compute',
]
GENERAL_HW_KW = [
    'chip', 'robot', 'robotic', 'hardware', 'device', 'processor',
    'sensor', 'semiconductor', 'gpu', 'tpu', 'autonomous',
    'drone', 'embodied', 'humanoid', 'ai pc', 'datacenter',
    'server', 'edge ai', 'quantum', 'silicon', 'wafer',
    'foundry', 'memory', 'hbm', 'accelerator', 'packaging',
    'exoskeleton', 'compute', 'llm serving',
]

def weighted_score(n):
    t = (n['title'] + ' ' + n.get('snippet', '')).lower()
    score = 0
    for kw in GENERAL_HW_KW:
        if kw in t:
            score += 1
    for kw in HIGH_IMPACT_KW:
        if kw in t:
            score += 3  # high-impact gets triple weight
    return score
```

### Recency Boost for Daily Digests

When scoring for a daily digest, boost articles from today/yesterday to ensure freshness:
```python
from datetime import datetime, timedelta
today = datetime.now().strftime('%Y/%m/%d')
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y/%m/%d')
day2 = (datetime.now() - timedelta(days=2)).strftime('%Y/%m/%d')
if today in n.get('url', '') or yesterday in n.get('url', ''):
    score += 2
elif day2 in n.get('url', ''):
    score += 1
```

## Chinese Summary Patterns by Topic

When composing Chinese summaries from English titles, use these patterns:

| English Topic | Chinese Pattern |
|---|---|
| NVIDIA/GPU news | "英伟达动态：{核心内容}" |
| AMD news | "AMD动态：{核心内容}" |
| Intel news | "英特尔动态：{核心内容}" |
| Humanoid robots | "人形机器人进展：{核心内容}" |
| General robotics | "机器人领域：{核心内容}" |
| Chips/semiconductors | "芯片/半导体动态：{核心内容}" |
| Quantum computing | "量子计算突破：{核心内容}" |
| Tesla | "特斯拉动态：{核心内容}" |
| Apple | "苹果动态：{核心内容}" |
| Datacenter/infrastructure | "数据中心/算力：{核心内容}" |
| Funding/IPO | "融资/上市：{核心内容}" |

## Feishu Message Format Template

```
🤖 AI硬件行业日报 | YYYY-MM-DD

1️⃣ [中文标题]
📌 [一句话中文摘要]
🔗 [原文链接]
📰 来源: [媒体名称]

...（共5条）

💡 今日洞察：[一句话行业趋势总结]
```
