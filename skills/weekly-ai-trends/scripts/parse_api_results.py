#!/usr/bin/env python3
"""Parse GitHub API JSON files for weekly-ai-trends skill.

Usage: python3 parse_api_results.py [N]
  N = number of top repos to output (default: 30)

Reads /tmp/trends_created.json, trends_pushed.json, trends_mid.json, trends_mcp.json
Output: sorted, deduplicated repo list to stdout
Diagnostics to stderr.
"""

import json, re, sys, os

def safe_json(path):
    """Read JSON stripping control characters that break json.loads()."""
    with open(path, 'r', errors='replace') as f:
        content = f.read()
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
    return json.loads(content)

FILES = {
    'created': '/tmp/trends_created.json',
    'pushed': '/tmp/trends_pushed.json',
    'mid': '/tmp/trends_mid.json',
    'mcp': '/tmp/trends_mcp.json',
}

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    all_repos = {}

    for label, path in FILES.items():
        if not os.path.exists(path):
            print(f"[warn] {path} not found, skipping", file=sys.stderr)
            continue
        try:
            data = safe_json(path)
            items = data.get('items', [])
            print(f"[{label}] total_count={data.get('total_count', '?')}, items={len(items)}", file=sys.stderr)
            for item in items:
                full_name = item.get('full_name', '')
                if not full_name or full_name in all_repos:
                    if full_name in all_repos:
                        all_repos[full_name]['labels'].add(label)
                    continue
                all_repos[full_name] = {
                    'name': full_name,
                    'stars': item.get('stargazers_count', 0),
                    'description': (item.get('description') or '').strip(),
                    'language': item.get('language') or '',
                    'created_at': item.get('created_at', ''),
                    'pushed_at': item.get('pushed_at', ''),
                    'url': item.get('html_url', ''),
                    'labels': {label},
                    'topics': item.get('topics', []),
                }
        except Exception as e:
            print(f"[error] {path}: {e}", file=sys.stderr)

    sorted_repos = sorted(all_repos.values(), key=lambda x: x['stars'], reverse=True)

    for i, r in enumerate(sorted_repos[:n]):
        labels = ','.join(r['labels'])
        print(f"{i+1}. {r['name']} | ⭐{r['stars']} | {r['language']} | labels:[{labels}] | created:{r['created_at'][:10]} pushed:{r['pushed_at'][:10]}")
        desc = r['description'][:150] if r['description'] else '(no description)'
        print(f"   {desc}")
        topics = ', '.join(r['topics'][:5]) if r['topics'] else ''
        if topics:
            print(f"   topics: {topics}")
        print()

    print(f"\nTotal unique repos: {len(all_repos)}", file=sys.stderr)

if __name__ == '__main__':
    main()
