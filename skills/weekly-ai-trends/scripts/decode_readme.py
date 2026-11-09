#!/usr/bin/env python3
"""Decode base64 README from GitHub API JSON response.

Usage: python3 decode_readme.py /tmp/readme.json [max_chars]
"""

import json, base64, re, sys

def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else '/tmp/readme.json'
    max_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

    with open(filepath, 'r', errors='replace') as f:
        data = json.load(f)

    content = base64.b64decode(data['content']).decode('utf-8', errors='replace')
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)

    print(content[:max_chars])

if __name__ == '__main__':
    main()
