---
name: chinese-political-news-scraper
category: research
description: Scrape and compile Chinese political/current affairs news (时政新闻) from domestic mainstream sources. Use when the user requests recent Chinese political news, daily news digests in Chinese, or 时政类新闻汇总.
trigger: "User asks for 时政新闻, 最新时政, 国内新闻top N, 24小时时政要闻, or similar Chinese political/news digest requests"
---

# Chinese Political News Scraper

Scrape and compile Chinese political/current affairs news from domestic mainstream sources.

## Environment Constraints

- ❌ **web_search** tool is NOT available in this environment
- ✅ **browser_navigate** works on Chinese news sites (腾讯新闻, 澎湃新闻, 新华网)
- ✅ **browser_snapshot** (full=true) extracts headlines and structure
- ✅ **browser_scroll** + repeated snapshots needed — pages truncate at ~200 elements

## Reliable Sources (Verified)

### 1. 澎湃新闻 (thepaper.cn) — Best for 时政
- **URL**: `https://www.thepaper.cn/`
- **Strengths**: Dedicated 时政 channel, hot rankings (热榜 1-15+), clear timestamps
- **Structure**: 推荐 feed → 深度 → 视频 → 热榜 sidebar → 时事/国际 sections
- **Pagination**: Scroll down + `browser_snapshot(full=true)` to load more items

### 2. 腾讯新闻 (news.qq.com) — Best for 热点精选
- **URL**: `https://news.qq.com/`
- **Strengths**: 热点精选 panel with source attribution + time stamps (e.g., "1小时前", "38分钟前")
- **Structure**: Top banner → 热点精选 (5 items with carousel) → feed with view/comment counts
- **Tip**: Click counts (e.g., "2261", "3695") are useful for ranking/popularity sorting

### 3. 新华网时政 (xinhuanet.com/politics) — Best for 官方权威
- **URL**: `https://www.xinhuanet.com/politics/`
- **Strengths**: Official state news, 国务院/部委 announcements, 人事任免, policy documents
- **Structure**: 专题 banners → 时政联播 → 新闻列表 → 人事 → 反腐 → 视频
- **Note**: Heavier pages, may take longer to load

### 4. 备选: 人民网 (people.com.cn)
- **URL**: `http://politics.people.com.cn/`
- May work if above sources are insufficient

## Scraping Workflow

```
1. Navigate to 澎湃新闻 → snapshot → scroll → snapshot (get 20+ items)
2. Navigate to 腾讯新闻 → snapshot → scroll → snapshot (get 20+ items)
3. Navigate to 新华网时政 → snapshot (get 30+ items)
4. Deduplicate across sources (same story from different outlets = 1 item)
5. Categorize: 时政要闻 / 国际时政 / 国内政经社会
6. Rank by: recency + prominence (top position = higher rank) + engagement (click counts)
7. Format output
```

## Output Format

```
### 🔴 时政要闻（Top 1-N）
1. **标题** — 一句话补充说明
2. **标题** — 一句话补充说明
...

### 🌍 国际时政（Top N-N）
...

### 🏛️ 国内政经与社会（Top N-N）
...

> 📊 数据来源：澎湃新闻、新华网、腾讯新闻、观察者网、央视新闻等
```

## Pitfalls

- **web_search is unavailable** — must use browser_navigate directly to news sites
- **Snapshots truncate** — always call `browser_snapshot(full=true)` after scrolling to get more items
- **Deduplication is critical** — same story appears on multiple sites; merge into one entry
- **Timestamps vary by source** — 腾讯新闻 shows relative ("1小时前"), 澎湃 shows absolute, 新华网 often shows no time. Normalize mentally when ranking.
- **Don't navigate to sub-pages** — the homepage/category page has enough headlines; individual article pages are slower and add no value for a digest
- **Categorize aggressively** — user asked for "时政类" specifically; exclude entertainment, sports, pure tech unless they have political significance
- **Source attribution matters** — when possible, note which outlet broke the story (e.g., "观察者网", "央视新闻", "新华社权威快报")

---

## Sub-section: Excel Generation & Feishu Delivery (from daily-news-to-feishu)
When user wants results as an Excel file (.xlsx) delivered via Feishu:

### User Preference: Excel, NOT Bitable
When user asks for "表格", generate `.xlsx` with `openpyxl` and send via `send_message` with `MEDIA:/path/to/file.xlsx`.
Do NOT use Bitable API — current Feishu app lacks `sheets:spreadsheet` write permissions (returns 404).

### Excel Generation Pattern
```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
wb = Workbook()
ws = wb.active
ws.title = "新闻Top30"
# Headers: 序号, 新闻标题, 新闻摘要, 来源
# Styled with blue header, borders, column widths: 8/45/80/15
```

### Delivery
```
send_message(message="已为您生成Excel表格...\n\nMEDIA:/root/News_Top30.xlsx", target="feishu:...")
```
Always deliver immediately — user complained "我咋没收到" when file wasn't sent.

### Extended Source Categories (from daily-news-to-feishu)
Beyond political news, also scrape:
- 科技: `https://news.qq.com/ch/tech/`
- 健康/科学: `https://news.qq.com/ch/health/`
