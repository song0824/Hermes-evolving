# GitHub API Patterns for weekly-ai-trends

## Date calculation
```bash
date -d "7 days ago" +%Y-%m-%d
```

## Four parallel queries (run simultaneously)
```bash
CUTOFF=$(date -d "7 days ago" +%Y-%m-%d)

# New repos this week
curl -s -o /tmp/trends_created.json "https://api.github.com/search/repositories?q=created:>${CUTOFF}+stars:>50+AI+agent+OR+LLM+OR+framework+OR+MCP&sort=stars&order=desc&per_page=25"

# Active repos with recent pushes
curl -s -o /tmp/trends_pushed.json "https://api.github.com/search/repositories?q=pushed:>${CUTOFF}+stars:>500+AI+agent+OR+LLM+OR+skill+OR+harness&sort=stars&order=desc&per_page=15"

# Mid-tier emerging projects
curl -s -o /tmp/trends_mid.json "https://api.github.com/search/repositories?q=pushed:>${CUTOFF}+stars:200..2000+AI+OR+agent+OR+LLM&sort=stars&order=desc&per_page=25"

# MCP ecosystem
curl -s -o /tmp/trends_mcp.json "https://api.github.com/search/repositories?q=pushed:>${CUTOFF}+stars:>100+MCP+OR+model+context+protocol&sort=stars&order=desc&per_page=15"
```

## README fetching (unauthenticated, 10 req/min limit)
```bash
python3 scripts/fetch_readmes.py yetone/cumora CopilotKit/OpenBot notte-labs/notte ...
```

## Repo name gotchas
- GitHub org names may vary: `nottelabs/notte` (correct) vs `notte-labs/notte` (404)
- Always verify repo existence with a quick HEAD check or API call before fetching READMEs
- If a repo returns 404, try searching: `curl -s "https://api.github.com/search/repositories?q=<keyword>&sort=stars&order=desc&per_page=3"`
