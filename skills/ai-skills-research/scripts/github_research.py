#!/usr/bin/env python3
"""AI Agent Skills Research — consolidated Phase 1 + Phase 2 script.

Run as a single invocation to avoid GitHub API rate limit exhaustion.
Writes results to /tmp/ai_skills_results.json.

Usage: python3 /tmp/ai_skills_research.py
"""

import json
import urllib.request
import urllib.parse
import base64
import sys
import time
from datetime import datetime, timedelta

SEARCH_QUOTA = 10
CORE_QUOTA = 60

EXCLUDE = {
    "langchain-ai/langchain", "langflow-ai/langflow", "dify-ai/dify",
    "open-webui/open-webui", "comfyui", "crewai", "openclaw/moltbot",
    "wasp-lang/open-saas", "farion1231/cc-switch", "danny-avila/LibreChat",
    "dair-ai/Prompt-Engineering-Guide", "Shubhamsaboo/awesome-llm-apps",
    "calesthio/OpenMontage", "googleworkspace/cli", "skalesapp/skales",
    "veniceai/skills", "vercel-labs/skills", "multica-ai/andrej-karpathy-skills",
    "Graphify-Labs/graphify", "hesreallyhim/awesome-claude-code",
    "kepano/obsidian-skills", "datopian/portaljs",
}

KNOWN_BIG_REPOS = [
    "anthropics/skills", "obra/superpowers", "JuliusBrussee/caveman",
    "sickn33/agentic-awesome-skills", "OthmanAdi/planning-with-files",
    "ruvnet/ruflo", "microsoft/SkillOpt",
]

SEARCH_QUERIES = [
    '"SKILL.md" agent sort:stars',
    '"SKILL.md" sort:stars',
    '"agent skills" framework sort:stars',
    '"SKILL.md" mcp sort:stars',
]

def api_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "AI-Skills-Research")
    try:
        resp = urllib.request.urlopen(url, timeout=15)
        remaining = int(resp.headers.get("X-RateLimit-Remaining", "0"))
        return json.loads(resp.read().decode()), remaining
    except urllib.error.HTTPError as e:
        remaining = int(e.headers.get("X-RateLimit-Remaining", "0"))
        if e.code == 403:
            print(f"  [403] remaining={remaining}", file=sys.stderr)
            return None, remaining
        elif e.code == 404:
            return None, remaining
        return None, remaining
    except Exception as e:
        print(f"  [ERR] {e}", file=sys.stderr)
        return None, 0

def github_search(query, page=1):
    q = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=30&page={page}"
    data, remaining = api_get(url)
    return data.get("items", []) if data else [], remaining

def get_repo_details(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    data, remaining = api_get(url)
    if not data:
        return None, remaining
    result = {
        "full_name": data.get("full_name", ""),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "issues": data.get("open_issues_count", 0),
        "description": data.get("description", ""),
        "pushed_at": data.get("pushed_at", ""),
        "language": data.get("language", ""),
    }
    commits_url = f"https://api.github.com/repos/{owner}/{repo}/stats/commit_activity"
    commits_data, r2 = api_get(commits_url)
    remaining = r2
    if commits_data and isinstance(commits_data, list):
        result["commits_4wk"] = sum(w.get("total", 0) for w in commits_data[-4:])
    else:
        result["commits_4wk"] = -1
    return result, remaining

# Phase 1
all_repos = {}
remaining = SEARCH_QUOTA
for query in SEARCH_QUERIES:
    if remaining < 2:
        break
    items, remaining = github_search(query)
    for item in items:
        fn = item["full_name"]
        if fn not in EXCLUDE and fn not in all_repos:
            all_repos[fn] = {"full_name": fn, "stars": item.get("stargazers_count", 0),
                            "description": item.get("description", "")}
    time.sleep(1)

for fn in KNOWN_BIG_REPOS:
    if fn in all_repos:
        continue
    owner, repo = fn.split("/")
    url = f"https://api.github.com/repos/{owner}/{repo}"
    data, remaining = api_get(url)
    if data:
        all_repos[fn] = {"full_name": fn, "stars": data.get("stargazers_count", 0),
                        "description": data.get("description", "")}
    time.sleep(1)

# Phase 2
sorted_repos = sorted(all_repos.values(), key=lambda x: x.get("stars", 0), reverse=True)
detailed = []
for repo_info in sorted_repos[:15]:
    if remaining < 5:
        repo_info["rate_limited"] = True
        detailed.append(repo_info)
        continue
    fn = repo_info["full_name"]
    owner, repo = fn.split("/")
    details, remaining = get_repo_details(owner, repo)
    if details:
        repo_info.update(details)
        detailed.append(repo_info)
    else:
        repo_info["rate_limited"] = True
        detailed.append(repo_info)
    time.sleep(1)

# Output
output = {"timestamp": datetime.now().isoformat(), "repos": detailed,
          "all_found": [{"full_name": r["full_name"], "stars": r.get("stars", 0)} for r in sorted_repos[:20]]}
with open("/tmp/ai_skills_results.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

for i, r in enumerate(detailed[:10], 1):
    print(f"{i}. {r['full_name']} — {r['stars']}★ | {r.get('description', '')[:80]}")
