#!/usr/bin/env python3
"""
GitHub AI Agent Skills Research Script — v2
Fetches repo metadata, README previews, recent issues, and commit activity.
Auto-populates Phase 2 targets from Phase 1 search results (top 15 by stars).
Handles rate limit exhaustion gracefully.
Usage: python3 github_research.py

Outputs JSON to stdout with all research data.
"""

import urllib.request as ureq, urllib.error as uerr, json, time, base64, sys, urllib.parse

# Phase 1: Search queries (broad coverage of SKILL.md ecosystem)
SEARCH_QUERIES = [
    '"SKILL.md" agent sort:stars',
    '"SKILL.md" AI agent sort:stars',
    'pushed:>2026-04-01 SKILL.md agent sort:stars',
    'pushed:>2026-04-01 "SKILL.md" sort:stars',
    '"SKILL.md" mcp sort:stars',
    'agent skills marketplace sort:stars',
    '"SKILL.md" claude sort:stars',
    'agent skills codex sort:stars',
    'awesome-copilot sort:stars',
]
requests_used = 0

def search_github(query, per_page=25):
    """Search GitHub repos. Returns list of repo dicts."""
    global requests_used
    encoded = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={encoded}&per_page={per_page}"
    req = ureq.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    resp = ureq.urlopen(req)
    # Track rate limit
    remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
    requests_used += 1
    print(f"  Rate limit remaining: {remaining} (total used: {requests_used})", file=sys.stderr)
    data = json.loads(resp.read())
    return data.get("items", []), data.get("total_count", 0)

def fetch_readme(repo, max_chars=600):
    """Fetch and decode README content."""
    global requests_used
    url = f"https://api.github.com/repos/{repo}/readme"
    req = ureq.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    resp = ureq.urlopen(req)
    remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
    requests_used += 1
    data = json.loads(resp.read())
    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return content[:max_chars]

def fetch_recent_issues(repo, count=5):
    """Fetch recent open issues with labels."""
    global requests_used
    url = f"https://api.github.com/repos/{repo}/issues?state=open&sort=created&direction=desc&per_page={count}"
    req = ureq.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    resp = ureq.urlopen(req)
    remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
    requests_used += 1
    issues = json.loads(resp.read())
    return [{"title": i["title"], "labels": [l["name"] for l in i.get("labels", [])]} for i in issues[:count]]

def fetch_commit_activity(repo):
    """Fetch 4-week commit total. Returns int or None."""
    global requests_used
    url = f"https://api.github.com/repos/{repo}/stats/commit_activity"
    req = ureq.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    resp = ureq.urlopen(req)
    remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
    requests_used += 1
    data = json.loads(resp.read())
    if isinstance(data, list) and len(data) > 0:
        return sum(w["total"] for w in data[-4:])
    return None

def research_repos(repos, sleep_seconds=7):
    """Research a list of repos with rate limiting. Gracefully degrades on 403."""
    results = []
    rate_limited = False
    for i, repo in enumerate(repos):
        if rate_limited:
            result = {"repo": repo, "readme_preview": "Rate limited — use browser_navigate fallback", "recent_issues": "Rate limited", "commits_4wk": None, "commit_status": "Rate limited"}
            results.append(result)
            continue
        time.sleep(sleep_seconds)
        print(f"Fetching {repo} ({i+1}/{len(repos)})", file=sys.stderr)
        
        result = {"repo": repo}
        
        try:
            result["readme_preview"] = fetch_readme(repo)
        except uerr.HTTPError as e:
            if e.code == 403:
                rate_limited = True
            result["readme_preview"] = f"Error: {e}"
        except Exception as e:
            result["readme_preview"] = f"Error: {e}"
        
        try:
            result["recent_issues"] = fetch_recent_issues(repo)
        except uerr.HTTPError as e:
            if e.code == 403:
                rate_limited = True
            result["recent_issues"] = f"Error: {e}"
        except Exception as e:
            result["recent_issues"] = f"Error: {e}"
        
        try:
            commits = fetch_commit_activity(repo)
            result["commits_4wk"] = commits
            result["commit_status"] = "unknown" if commits is None else str(commits)
        except uerr.HTTPError as e:
            if e.code == 403:
                rate_limited = True
            result["commits_4wk"] = None
            result["commit_status"] = f"Error: {e}"
        except Exception as e:
            result["commits_4wk"] = None
            result["commit_status"] = f"Error: {e}"
        
        results.append(result)
    
    return results

if __name__ == "__main__":
    # Phase 1: Search
    print("=== PHASE 1: SEARCH ===", file=sys.stderr)
    all_repos = {}
    for q in SEARCH_QUERIES:
        try:
            items, total = search_github(q)
            print(f"Query: {q} -> {total} results", file=sys.stderr)
            for r in items:
                fn = r["full_name"]
                if fn not in all_repos or r["stargazers_count"] > all_repos[fn]["stars"]:
                    all_repos[fn] = {
                        "full_name": fn,
                        "stars": r["stargazers_count"],
                        "description": r.get("description", ""),
                        "pushed_at": r.get("pushed_at", ""),
                        "forks": r.get("forks_count", 0),
                        "open_issues": r.get("open_issues_count", 0),
                    }
        except uerr.HTTPError as e:
            if e.code == 403:
                print(f"Query RATE-LIMITED: {q} (403). Remaining Phase 1 queries will also fail.", file=sys.stderr)
                break  # Stop Phase 1 early — save quota for Phase 2
            print(f"Query FAILED: {q} -> {e}", file=sys.stderr)
    
    # Auto-populate Phase 2: top 15 repos by stars
    sorted_repos = sorted(all_repos.values(), key=lambda x: x["stars"], reverse=True)
    DETAIL_REPOS = [r["full_name"] for r in sorted_repos[:15]]
    
    print(f"\nTop 15 repos by stars (auto-selected for Phase 2):", file=sys.stderr)
    for r in sorted_repos[:15]:
        print(f"  {r['full_name']}: {r['stars']} stars", file=sys.stderr)
    
    # Phase 2: Deep research on auto-selected repos
    if DETAIL_REPOS:
        print(f"\n=== PHASE 2: DEEP RESEARCH ({len(DETAIL_REPOS)} repos) ===", file=sys.stderr)
        results = research_repos(DETAIL_REPOS)
        
        # Merge Phase 1 basic info into Phase 2 results
        for r in results:
            if r["repo"] in all_repos:
                r["basic"] = all_repos[r["repo"]]
        
        print("\n=== JSON OUTPUT ===")
        print(json.dumps(results, indent=2))
