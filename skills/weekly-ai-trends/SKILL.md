---
name: weekly-ai-trends
description: 每周搜索并总结 GitHub 上最新的 AI 技术、框架、Agent Skills 和趋势，整理成 Top 5 排行榜。输出纯文本+Emoji 排版，适配飞书。
---

# Weekly AI Trends Research Skill

## Trigger
User asks for the latest AI trends, weekly AI roundup, GitHub AI trends, or wants to see what's new in AI/tech. For **industry news digests** (TechCrunch, Wired, etc.) with Feishu delivery, see `tech-news-scraper` skill instead.

## Workflow

1. **Search GitHub (API via Terminal)**
   - Query 1 (new repos): `curl -s -o /tmp/trends_created.json "https://api.github.com/search/repositories?q=created:>YYYY-MM-DD+stars:>50+AI+agent+OR+LLM+OR+framework+OR+MCP&sort=stars&order=desc&per_page=25"`
   - Query 2 (active repos): `curl -s -o /tmp/trends_pushed.json "https://api.github.com/search/repositories?q=pushed:>YYYY-MM-DD+stars:>500+AI+agent+OR+LLM+OR+skill+OR+harness&sort=stars&order=desc&per_page=15"`
   - Query 3 (mid-tier emerging): `curl -s -o /tmp/trends_mid.json "https://api.github.com/search/repositories?q=pushed:>YYYY-MM-DD+stars:200..2000+AI+OR+agent+OR+LLM&sort=stars&order=desc&per_page=25"`
     — Note: the `stars:500..5000` range often returns 0 results when combined with `pushed`. Use `200..2000` with `AI` keyword for better yield.
   - Query 4 (MCP ecosystem): `curl -s -o /tmp/trends_mcp.json "https://api.github.com/search/repositories?q=pushed:>YYYY-MM-DD+stars:>100+MCP+OR+model+context+protocol&sort=stars&order=desc&per_page=15"`
     — MCP is a mature, high-signal category. Official SDKs (Python/TS/Go) + servers registry are always worth checking.
   - Parse downloaded JSON: use `python3 scripts/parse_api_results.py` — it handles control characters that break `json.loads()` (see Pitfalls).
   - For top candidates, batch-fetch READMEs: `python3 scripts/fetch_readmes.py owner1/repo1 owner2/repo2 ...` (see `scripts/fetch_readmes.py`). Uses 1s delays between requests to respect rate limits. Can handle 12+ repos in a single invocation (~2 min total).
   - Rate limit fallback: If you hit "API rate limit exceeded", wait 60s and retry with a narrower query (fewer results, tighter star range).

2. **Search GitHub Trending Page (FALLBACK ONLY)**
   - Browser navigation to github.com/trending is unreliable (CDP timeouts, connection refused).
   - Preferred: use the API queries above — they're faster and more structured.
   - If browser is needed: `curl -s -o /tmp/trending.html "https://github.com/trending?since=weekly" -H "User-Agent: Mozilla/5.0"` as a fallback.
   - **Parsing approach**: Extract `<article>` blocks from HTML, then regex each article for repo name (`href="/([^"]+?)"` + class Link check), description (`<p>` tag, strip HTML), language (`itemprop="programmingLanguage"`), and stars (`(\d+,?\d+)\s*stars?`). Filter out `login?`, `trending/`, and `sponsors/` hrefs — GitHub intermixes these with real repo articles.
   - See `scripts/parse_trending.py` for a reusable parser.

3. **Analyze & Synthesize**
   - For each top project, extract:
     - Name, Stars (approx) — GitHub API returns absolute star count, not weekly growth. Use ⭐ number as-is and infer "本周新创建" for brand-new repos or "本周活跃/发布 X.X" for existing repos with recent pushes.
     - Description & Core features
     - Why it's trending ("为什么火")
     - GitHub Link
   - Also compile "本周活跃项目速览" — list the top 5 most-starred repos that had recent pushes (from Query 2), showing they're still actively maintained.
   - Add "本周趋势观察" — 3-5 bullet-point trend observations synthesizing cross-repo patterns (e.g., "Agent 记忆层爆发", "MCP 生态成熟").

4. **Format Output (CRITICAL — Feishu Rules)**
   - **CRITICAL**: Do NOT use Markdown syntax (`#`, `**`, `*`, `-`, `|` tables, `` ` `` code blocks, `[link](url)`). Feishu cannot render them. This applies to ALL sections — do NOT use bold/italic/links anywhere in the final report, including the "趋势观察" summary. Write URLs as plain text (e.g., `https://github.com/...`).
   - Use Feishu-friendly rich text formatting:
     - Emojis for structure (🎬, 🌐, 🧠, 🎓, 🔓, 🐎, 🔗, 💡, 📦, 🚀)
     - `━━━━━━━━━━━━━━━━━━` as section dividers
     - **Punctuation and emoji must be preserved** — user explicitly requested both.
     - Feishu DOES support rich formatting — use emojis as visual bullets and section markers for clear hierarchy. Do NOT strip to bare text.
     - Use 1️⃣ 2️⃣ 3️⃣ emoji numbers for ordered lists (not `1.`, `-`, or `*` which render as markdown).
     - Include 工具介绍 (what it is), 为什么火 (why it's trending), and 🔗 GitHub link for each item.
     - End with a trend summary (💡 总结).

5. **Deliver to Feishu**
   - Direct plain text output with emojis, optimized for Feishu chat.

## Scripts
Scripts are bundled with this skill via `linked_files`. Access them with `skill_view(name='weekly-ai-trends', file_path='scripts/parse_api_results.py')` etc., or use the inline Python fallback below (often faster than locating files).

- `scripts/parse_api_results.py` — Parse all four GitHub API JSON files at once. Usage: `python3 scripts/parse_api_results.py [N]` where N defaults to 30. Strips control characters, deduplicates by full_name, merges labels. Output to stdout, diagnostics to stderr.
- `scripts/fetch_readmes.py` — Batch fetch READMEs for multiple repos. Usage: `python3 scripts/fetch_readmes.py owner/repo owner2/repo2 ...` or read from `/tmp/repo_list.txt`. Handles rate-limit retries (60s backoff). Uses `urllib.request` (no terminal pipe issues). 1.2s delay between requests. Saves consolidated output to `/tmp/readmes.json`.
- `scripts/decode_readme.py` — Decode base64 README from a single GitHub API JSON response. Usage: `python3 scripts/decode_readme.py /tmp/readme.json [max_chars]`.
- `scripts/parse_trending.py` — Parse GitHub trending HTML → JSON (repo, lang, desc, stars).

## Pitfalls
- **total_count vs per_page**: GitHub API `total_count` can be in the thousands (e.g., 2204 for pushed query) but `per_page` caps how many you see. Query 1 and 3 use `per_page=25` to maximize candidate pool; Query 2 (active repos) uses `per_page=15` since mega-repos dominate and the tail adds little signal.
- JSON control characters in GitHub API responses: GitHub repo descriptions can contain control characters (`\x00-\x1f`) that break `json.loads()` even with `strict=False`. Always strip them with `re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)` before parsing. Use `scripts/parse_api_results.py` which handles this automatically.
- Terminal output truncation: `terminal('cat /tmp/large.json')` truncates at ~50K chars, causing parse failures. Always read files with a Python script that opens them directly (`open(path)`), not via terminal cat.
- GitHub API pipe blocked: `curl | python3` pipes are flagged by the security scanner as [HIGH]. Always use `curl -s -o /tmp/data.json "URL"` then parse with a standalone script. This also applies to readme decoding — download the JSON first, decode base64 in a separate step.
- GitHub API rate limiting: Unauthenticated requests cap at 10 req/min from a single IP. After 3-4 queries in quick succession you may hit "API rate limit exceeded". Mitigation: (a) spread queries with small delays, (b) use narrower queries after hitting the limit (smaller per_page, tighter star range), (c) the limit resets within a minute.
- Browser navigation to GitHub trending is unreliable: CDP timeout and ERR_CONNECTION_CLOSED are common. The curl fallback (`curl -s -o /tmp/trending.html`) ALSO frequently times out at 30s even with User-Agent header. Treat the trending page as effectively unavailable — the API queries are the primary and usually sufficient source.
- browser_snapshot truncation: the trending page has 20+ articles but snapshots truncate at ~8000 chars. If using browser, use `browser_console` with DOM extraction (e.g., `document.querySelectorAll('article h2 a')`) to get complete repo lists.
- Always compute the date 7 days ago and use it in absolute `YYYY-MM-DD` format in API queries (e.g., `created:>2026-10-09`). Do NOT use `today-7d` or similar relative syntax — GitHub API requires ISO date.
- Don't rely on old trends; verify the creation/push dates.
- If a repo is too small (under 200 stars) but trending, explain why.
- Keep descriptions short, punchy, and focused on "Why it matters."
- Do NOT use Markdown.
- GitHub trending HTML description noise: the `<p>` tag in trending articles leaks UI text like "Sponsor", "Star", and "owner / repo" path strings. Always strip these after HTML tag removal. The `scripts/parse_trending.py` script handles this automatically — use it rather than manual regex.
- Parallel API discovery pattern: run all four queries (created, pushed, mid-tier, MCP) simultaneously for comprehensive coverage. MCP query reliably surfaces protocol-level innovations. Cross-reference results to catch repos appearing in multiple categories — these are your strongest Top 5 candidates.
- **Repo name verification**: GitHub org names in API results may not match what you expect (e.g., `nottelabs/notte` vs `notte-labs/notte`). Always use the exact `full_name` from API search results when fetching READMEs — never guess or reformat org/repo slugs. If a README fetch returns 404, search for the repo again to get the canonical name.
- **Null description handling**: GitHub API `description` field can be `null` (not empty string). Naive slicing like `item.get('description')[:120]` will raise `TypeError: 'NoneType' object is not subscriptable`. Always guard with: `d = item.get('description') or ''; return d[:N]` or use a helper function.
- **README fetching: use urllib, not terminal pipes**: The `curl | python3` pipe pattern is flagged as [HIGH] by the security scanner. Use `scripts/fetch_readmes.py` which uses `urllib.request` directly — no pipes, no terminal truncation, built-in rate-limit retry logic.
- **Fallback when scripts unavailable (PREFERRED — fast and reliable)**: Use `execute_code` with inline Python. Import from `hermes_tools` — use `open(path)` to read JSON files directly (never `terminal('cat ...')` which truncates at ~50K chars). Strip control characters with `re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)` before `json.loads(strict=False)`. The same `execute_code` approach works for README fetching: use `urllib.request` + `base64.b64decode` with 1.2s delays between requests. This avoids all file-path and terminal-pipe issues.