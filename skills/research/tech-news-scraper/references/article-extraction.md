# Article Extraction Techniques

## TechCrunch — Status Update (2026-08-24)

**All HTML-based extraction methods for TechCrunch have stopped working.** As of 2026-08-24:

- ❌ `fetch_article_summary()` (meta description extraction): Returns navigation chrome only, no `<meta name="description">` accessible
- ❌ `extract_paragraphs()` (`<p>` tag extraction): Returns navigation chrome only, no article `<p>` tags
- ❌ Googlebot UA fetch: Not tested recently, but standard UA no longer works; Googlebot UA may or may not still work
- ✅ RSS title only: The only reliable data source from TechCrunch

**Recommended approach**: Compose summaries from RSS titles alone. If deep content is needed, use the `browse` skill (GStack browser).

## Meta Description Extraction (for other sites)

```python
def fetch_article_summary(url, timeout=15):
    """Fetch meta description from article HTML. Works on some sites, NOT TechCrunch."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        html = resp.read().decode('utf-8', errors='replace')
        meta_m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not meta_m:
            meta_m = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']description["\']', html, re.IGNORECASE)
        if meta_m:
            return meta_m.group(1).strip()[:500]
    except:
        pass
    return ""
```

## `<p>` Tag Extraction (fallback for other sites)

```python
def extract_paragraphs(url, max_p=5, timeout=15):
    """Extract first N <p> tags from article HTML. Works on some sites, NOT TechCrunch."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        html = resp.read().decode('utf-8', errors='replace')
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        texts = []
        for p in paragraphs:
            text = re.sub(r'<[^>]+>', '', p).strip()
            if len(text) > 30:  # Skip short/nav paragraphs
                texts.append(text)
            if len(texts) >= max_p:
                break
        return ' '.join(texts)[:500]
    except:
        return ""
```

## Event/Promotional Noise Filtering

```python
def is_noise(title):
    """Filter conference/event promotional content from RSS feeds."""
    noise_kw = ['disrupt ', 'battlefield', 'ticket', 'early bird', 'save up',
                'applications close', 'apply to speak', 'exhibit at',
                'last day', 'days left', 'weeks left', 'apply before',
                'lock in', 'get in front of', 'second pass',
                'final 24 hours', 'two weeks left', '5 days left',
                '2 days left', '3 days', 'startup battlefield']
    tl = title.lower()
    return any(kw in tl for kw in noise_kw)
```

## CDATA-Aware RSS Parsing

```python
def parse_rss_cdata(xml):
    """Parse RSS with CDATA support for title and description."""
    items = []
    blocks = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    for block in blocks:
        title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', block, re.DOTALL)
        if not title_m:
            title_m = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
        link_m = re.search(r'<link>(.*?)</link>', block)
        desc_m = re.search(r'<description>\s*<!\[CDATA\[(.*?)\]\]>', block, re.DOTALL)
        if not desc_m:
            desc_m = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ''
        link = link_m.group(1).strip() if link_m else ''
        desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()[:500] if desc_m else ''
        if title and len(title) > 5:
            items.append({'title': title, 'url': link, 'snippet': desc})
    return items
```
