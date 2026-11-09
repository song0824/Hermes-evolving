#!/usr/bin/env python3
"""Batch fetch READMEs from GitHub API for weekly-ai-trends skill.

Usage: python3 fetch_readmes.py owner/repo owner2/repo2 ...
  Or: python3 fetch_readmes.py --file /tmp/repo_list.txt  (one repo per line)

Fetches README content via GitHub API, decodes base64, saves to /tmp/readmes.json.
Uses 1.2s delay between requests to respect rate limits.
Uses urllib (no terminal pipe issues). Handles rate-limit retries with 60s backoff.
"""

import urllib.request, json, time, base64, re, sys, os

OUTPUT = '/tmp/readmes.json'
DELAY = 1.2
MAX_CHARS = 3000

def fetch_readme(repo, max_retries=3):
    """Fetch and decode README for a single repo."""
    url = f"https://api.github.com/repos/{repo}/readme"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/vnd.github.v3+json',
    })

    for attempt in range(max_retries):
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            content = base64.b64decode(data['content']).decode('utf-8', errors='replace')
            # Strip control characters
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
            return content[:MAX_CHARS]
        except urllib.error.HTTPError as e:
            if e.code == 403 and attempt < max_retries - 1:
                # Rate limited — wait and retry
                wait = 60 * (attempt + 1)
                print(f"[warn] Rate limited for {repo}, waiting {wait}s...")
                time.sleep(wait)
                continue
            elif e.code == 404:
                return None  # No README
            else:
                raise
    return None

def main():
    repos = []

    # Check for --file flag
    args = sys.argv[1:]
    if args and args[0] == '--file':
        filepath = args[1] if len(args) > 1 else '/tmp/repo_list.txt'
        if os.path.exists(filepath):
            with open(filepath) as f:
                repos = [line.strip() for line in f if line.strip() and '/' in line]
    else:
        repos = args

    if not repos:
        print("Usage: fetch_readmes.py owner/repo ...  OR  fetch_readmes.py --file /tmp/repo_list.txt")
        sys.exit(1)

    results = {}
    for i, repo in enumerate(repos):
        print(f"[{i+1}/{len(repos)}] Fetching {repo}...")
        content = fetch_readme(repo)
        if content:
            results[repo] = content
            print(f"  ✓ {len(content)} chars")
        else:
            results[repo] = None
            print(f"  ✗ No README or error")
        if i < len(repos) - 1:
            time.sleep(DELAY)

    with open(OUTPUT, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {sum(1 for v in results.values() if v)} READMEs to {OUTPUT}")

if __name__ == '__main__':
    main()
