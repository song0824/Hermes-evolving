#!/usr/bin/env python3
"""Parse GitHub trending HTML to JSON (fallback when API is unavailable).

Usage: python3 parse_trending.py [html_file]
  Default: /tmp/trending.html

Output: JSON to stdout with repo, language, description, stars.
"""

import re, json, sys, html as html_module

def parse_trending(html_path):
    with open(html_path, 'r', errors='replace') as f:
        content = f.read()

    # Find all article blocks
    articles = re.findall(r'<article[^>]*>(.*?)</article>', content, re.DOTALL)

    repos = []
    for article in articles:
        # Repo name: look for <a href="/owner/repo"> inside h2
        repo_match = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+?)"[^>]*class="[^"]*Link[^"]*"', article)
        if not repo_match:
            # Fallback: any href in h2 that's not login/trending/sponsors
            repo_match = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+?)"', article)
            if repo_match and any(x in repo_match.group(1) for x in ['login?', 'trending/', 'sponsors/']):
                continue

        if not repo_match:
            continue

        repo_name = repo_match.group(1).strip()
        if any(x in repo_name for x in ['login?', 'trending/', 'sponsors/', 'signup']):
            continue

        # Language
        lang_match = re.search(r'itemprop="programmingLanguage"[^>]*>([^<]+)<', article)
        language = lang_match.group(1).strip() if lang_match else ''

        # Description: <p> tag, then strip HTML and noise
        desc_match = re.search(r'<p[^>]*>(.*?)</p>', article, re.DOTALL)
        description = ''
        if desc_match:
            # Strip HTML tags
            desc = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
            # Remove noise words that leak from GitHub UI
            desc = re.sub(r'\b(Sponsor|Star|Sponsors)\b', '', desc, flags=re.IGNORECASE)
            # Remove repo name path (e.g., "owner / repo")
            desc = re.sub(r'\s*[/\\]\s*', ' ', desc)
            desc = ' '.join(desc.split())  # Normalize whitespace
            # If description is just the repo name repeated, skip
            repo_parts = set(repo_name.lower().split('/'))
            desc_words = set(desc.lower().split())
            if desc_words <= repo_parts or not desc:
                description = ''
            else:
                description = desc

        # Stars
        stars_match = re.search(r'(\d+,?\d+)\s*stars?', article)
        stars_str = stars_match.group(1).replace(',', '') if stars_match else '0'
        stars = int(stars_str)

        repos.append({
            'repo': repo_name,
            'language': language,
            'description': description,
            'stars': stars,
        })

    return repos

def main():
    html_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/trending.html'
    repos = parse_trending(html_path)
    print(json.dumps(repos, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
