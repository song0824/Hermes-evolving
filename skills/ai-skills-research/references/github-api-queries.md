# GitHub API Query Patterns for AI Skills Research

## All-time popular (by stars)
```
curl -s "https://api.github.com/search/repositories?q=AI+agent+skills+framework&sort=stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=mcp+server+skill&sort:stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=awesome+AI+agent+skills&sort=stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=SKILL.md+agent&sort:stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=claude+code+skills&sort=stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=%22SKILL.md%22+mcp+sort:stars&sort=stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=agent+skills+marketplace+sort:stars&sort:stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=awesome-copilot+sort:stars&sort=stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=agent+skills+codex+sort:stars&sort=stars&order=desc&per_page=10"
```

## Trending keywords (emerging concepts)
```
curl -s "https://api.github.com/search/repositories?q=harness+engineering+agent&sort=stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=loop+engineering+ai+agent&sort=stars&order=desc&per_page=10"
curl -s "https://api.github.com/search/repositories?q=context+engineering+ai&sort=stars&order=desc&per_page=5"
curl -s "https://api.github.com/search/repositories?q=agent+apprenticeship&sort=stars&order=desc&per_page=5"
```

## Recent creations (last N weeks) — for "最新" requests
```
# Replace 2026-06-10 with the appropriate date (2 weeks ago)
curl -s "https://api.github.com/search/repositories?q=created:>2026-06-10+AI+agent+OR+LLM+OR+model&sort=stars&order=desc&per_page=10"
```

## Recently active (pushed recently)
```
curl -s "https://api.github.com/search/repositories?q=pushed:>2026-06-18+topic:llm+OR+topic:ai+sort:stars&order=desc&per_page=10"
```

## Read README content (base64 decode required)
```
curl -s "https://api.github.com/repos/{owner}/{repo}/readme" | python3 -c "
import json, sys, base64
data = json.load(sys.stdin)
if 'content' in data:
    print(base64.b64decode(data['content']).decode('utf-8'))
"
```

## Parse results
```
curl -s "..." | python3 -c "
import json, sys
data = json.load(sys.stdin)
for i, repo in enumerate(data.get('items', []), 1):
    print(f'{i}. {repo[\"full_name\"]} ⭐ {repo[\"stargazers_count\"]} | created:{repo[\"created_at\"]} | {repo[\"description\"]}')
"
```

## Rate Limit Tracking
Unauthenticated GitHub API: 60 requests/hour. Each search, repo detail, README, issues, and commit_activity call counts as 1 request.
- Phase 1 (6 search queries) = ~6 requests
- Phase 2 (15 repos × 3 calls each: README + issues + commits) = ~45 requests
- **Total: ~51 requests** — close to the 60/hr limit
- Check `X-RateLimit-Remaining` header after each call. When < 10, stop making new API calls and synthesize from existing data.
- The v2 `github_research.py` script auto-tracks this and prints remaining quota after each request.
