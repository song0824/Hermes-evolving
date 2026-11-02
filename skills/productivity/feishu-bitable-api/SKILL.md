---
name: feishu-bitable-api
description: Read Feishu/Lark Bitable (多维表格) data via Open API. Covers resolving wiki nodes to bitable tokens, fetching fields, and reading records with pagination.
category: productivity
---

# Feishu Bitable (多维表格) API Reader

Use this skill to read Feishu Bitable (spreadsheet/database-like tables) via the Open API when browser access requires login.

## Prerequisites
- Feishu Open Platform App ID and App Secret (from `~/.hermes/config.yaml` under `platforms.feishu.extra`)
- App must have `bitable:app:readonly` permission
- App must be added as a member/collaborator of the target wiki/bitable

## Workflow

### Step 1: Get tenant_access_token
```python
import urllib.request, json

APP_ID = "cli_xxx"
APP_SECRET = "xxx"
token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
token_body = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode()
req = urllib.request.Request(token_url, data=token_body, headers={"Content-Type": "application/json"})
token_resp = json.loads(urllib.request.urlopen(req).read(), strict=False)
token = token_resp.get("tenant_access_token", "")
```

### Step 2: Resolve wiki node to get bitable token
The wiki URL format: `https://xxx.feishu.cn/wiki/{wiki_node_token}?table={table_id}&view={view_id}`

1. Extract `wiki_node_token` from the URL (the part after `/wiki/`)
2. Resolve the wiki node:
```python
wiki_token = "BqLuwv4fNiAUERkLG2Yc6YO0nxd"  # from URL
node_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?obj_type=wiki&token={wiki_token}"
req = urllib.request.Request(node_url)
req.add_header("Authorization", f"Bearer {token}")
node_resp = json.loads(urllib.request.urlopen(req).read(), strict=False)
node = node_resp.get("data", {}).get("node", {})
bitable_token = node.get("obj_token")  # e.g., "JmEHb9orfaOmYssOwETcNncYnWd"
obj_type = node.get("obj_type")  # "bitable"
```
- If `obj_type` is `"bitable"`, use `obj_token` as the bitable app token
- If `obj_type` is `"docx"`, use the `feishu-doc-api` skill instead

### Step 3: Get table fields
```python
table_id = "tbl9c4NAOuRuIPpt"  # from URL query param
fields_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{bitable_token}/tables/{table_id}/fields?page_size=100"
req = urllib.request.Request(fields_url)
req.add_header("Authorization", f"Bearer {token}")
fields_resp = json.loads(urllib.request.urlopen(req).read(), strict=False)
fields = fields_resp.get('data', {}).get('items', [])
for f in fields:
    print(f"{f['field_name']} (type={f['type']}, id={f['field_id']})")
```

Field types:
- `1`: Text (文本)
- `2`: Number (数字)
- `3`: Single/Multi-select (单选/多选) — values are arrays of `{name, id}` objects
- `5`: Date (日期) — values are millisecond timestamps
- `7`: URL
- `11`: Person (人员) — values are arrays of `{name, id}` objects
- `15`: Checkbox (复选框)
- `17`: Phone
- `18`: Reference (引用) — links to other records

### Step 4: Get records (with pagination)
```python
import urllib.request, json

bitable_token = "JmEHb9orfaOmYssOwETcNncYnWd"
table_id = "tbl9c4NAOuRuIPpt"

records_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{bitable_token}/tables/{table_id}/records?page_size=500"
req = urllib.request.Request(records_url)
req.add_header("Authorization", f"Bearer {token}")
records_resp = json.loads(urllib.request.urlopen(req).read(), strict=False)
all_records = records_resp.get('data', {}).get('items', [])
has_more = records_resp.get('data', {}).get('has_more', False)
page_token = records_resp.get('data', {}).get('page_token', '')

while has_more:
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{bitable_token}/tables/{table_id}/records?page_size=500&page_token={page_token}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    resp = json.loads(urllib.request.urlopen(req).read(), strict=False)
    all_records.extend(resp.get('data', {}).get('items', []))
    has_more = resp.get('data', {}).get('has_more', False)
    page_token = resp.get('data', {}).get('page_token', '')
```

### Step 5: Parse record fields
Each record has structure:
```json
{
  "record_id": "recXXX",
  "fields": {
    "Field Name": value,
    ...
  }
}
```

Field value parsing:
- **Text**: string
- **Number**: number (float/int). **Caveat**: fields formatted with a suffix (e.g. `%` for Percent) may return as strings like `"50%"` instead of raw numbers. Use `str(val).replace("%", "")` before `float()` conversion.
- **Select (type 3)**: `[{name: "Ongoing", id: "optXXX"}, ...]` — extract names with `[item.get('name', '') for item in val]`
- **Date (type 5)**: millisecond timestamp — convert with `datetime.fromtimestamp(val / 1000)`
- **Person (type 11)**: `[{name: "张三", id: "ou_XXX"}, ...]`
- **Checkbox (type 15)**: boolean (1/0 or True/False)
- **Phone (type 17)**: `{phone: "13800138000", region: "86"}`

Example parsing:
```python
from datetime import datetime

def get_text_val(field_val):
    if field_val is None: return ''
    if isinstance(field_val, str): return field_val
    if isinstance(field_val, list):
        return ', '.join([item.get('name', str(item)) for item in field_val])
    return str(field_val)

def get_date(field_val):
    if not field_val: return None, ''
    try:
        dt = datetime.fromtimestamp(field_val / 1000)
        return dt, dt.strftime('%Y-%m-%d')
    except:
        return None, str(field_val)

for r in all_records:
    f = r.get('fields', {})
    name = f.get('Project name', '')
    status = get_text_val(f.get('Status'))
    end_dt, end_str = get_date(f.get('End date'))
```

### Step 6: Filter records (optional)
The Bitable API supports `filter` parameter for server-side filtering:
```python
import urllib.parse

filter_body = {
    "filter": {
        "conjunction": "and",
        "conditions": [
            {"field_name": "Status", "operator": "is", "value": ["Ongoing"]}
        ]
    }
}
filter_str = json.dumps(filter_body)
records_url += "&filter=" + urllib.parse.quote(filter_str)
```

## Output to Feishu Docx Document

When asked to write analysis results to a Feishu document, use the docx block writing API. See `references/docx-writing.md` for the full API reference.

Quick pattern:
1. Create doc: `POST /docx/v1/documents` → get `document_id`
2. Build blocks: text blocks (type 2) for content, text separators for dividers. Use `content` (NOT `text`) in text_run. For heading-style text, use text blocks (type 2) with `bold: true` in text_element_style — heading blocks (type 3-11) may return error 1770029.
3. Write ALL batches to `{doc_id}/blocks/{doc_id}/children` — **do NOT use `position=after`** (causes "too deep level" error 1770005 after ~1000 blocks). The API auto-appends to end.
4. Batch size of 50 works reliably.
5. Grant access: `POST /drive/v1/permissions/{doc_id}/members?type=docx` with `member_type: openid` and `perm: full_access`

## Common Pitfalls
- **Permission error 99991672**: App needs `bitable:app:readonly` permission. Link: `https://open.feishu.cn/app/{app_id}/auth?q=bitable:app:readonly`
- **Wiki token ≠ bitable token**: The URL contains a wiki node token. Always resolve via `wiki/v2/spaces/get_node` first to get `obj_token`.
- **Date values are millisecond timestamps**: Divide by 1000 before passing to `datetime.fromtimestamp()`.
- **Select/Person fields are arrays**: Always check `isinstance(val, list)` before extracting names.
- **Pagination is mandatory**: max `page_size=500`. Check `has_more` and use `page_token`.
- **Large tables (>1500 records) — avoid execute_code stdout cap**: When paginating across many pages, the combined JSON can exceed execute_code's 50KB stdout limit. Instead of collecting all records in a Python variable, use `terminal()` to redirect each page's `curl` output to a temp file, then read the files afterward:
```bash
# In execute_code, use terminal() to save pages to disk:
terminal(f'curl -s "{url}" -H "Authorization: Bearer {token}" > /tmp/bitable_page{N}.json')
# Then read files:
with open("/tmp/bitable_page1.json") as f: data = json.load(f)
```
- **Reference (type 18) / Parent items field structure**: See `references/parent-items-extraction.md` for the complete extraction pattern covering all three variants (has text, has record_ids only, empty parent).
- **Empty/null fields**: Records may not have all fields populated. Use `.get()` with defaults.
- **Token expiry**: `tenant_access_token` expires in ~6600 seconds. If you get error **99991663** ("Invalid access token"), re-fetch the token immediately:
```python
token_resp = terminal('curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" -H "Content-Type: application/json" -d \'{"app_id": "...", "app_secret": "..."}\'')
token = json.loads(token_resp["output"])["tenant_access_token"]
```
- **User requests re-generating documents**: If the user says "重新生成一个文档" or "别在原先的上面改", ALWAYS create a brand new document and write to it. Do NOT try to delete + rewrite existing content — it's slower and error-prone. Just create fresh and share the new link.
- **Start date > End date (data entry errors)**: Some records have dates reversed. Always check and swap before calculating durations: `if start > end: start, end = end, start`.
- **Missing dates or owners**: Schedule tables often have records with missing `Start date`, `End date`, or `Owner`. Filter these out before aggregation and report the skip count.
- **Multiple owners per record**: A record can have multiple people in a Person field. When aggregating by person, iterate over all owners and add the same duration to each.
- **Docx writing — NEVER use `position=after`**: Using `position=after&block_id={last_block_id}` chains blocks as nested children rather than siblings. After ~1000 blocks, the document tree depth exceeds the limit and returns error 1770005 "too deep level in document". **Fix**: Always POST to `/documents/{doc_id}/blocks/{doc_id}/children` (no position param) for every batch. The API appends to the end automatically. Verified with 1620 blocks across 33 batches — all succeeded.

## Data Analysis Pattern: Aggregating by Person/Owner

When asked to summarize time, days, or workload from a schedule Bitable:

```python
import json
from datetime import datetime
from collections import defaultdict

person_days = defaultdict(float)
person_tasks = defaultdict(list)
skipped = 0

for r in records:
    f = r['fields']
    owners = f.get('Owner', [])
    start = f.get('Start date')
    end = f.get('End date')
    project = f.get('Project name', '')

    if not owners or not start or not end:
        skipped += 1
        continue

    # Fix reversed dates
    if start > end:
        start, end = end, start

    days = (end - start) / (1000 * 60 * 60 * 24)

    for owner in owners:
        name = owner.get('name', 'Unknown')
        person_days[name] += days
        person_tasks[name].append({
            'project': project,
            'days': days,
            'start': datetime.fromtimestamp(start/1000).strftime('%Y-%m-%d'),
            'end': datetime.fromtimestamp(end/1000).strftime('%Y-%m-%d')
        })

# Sort by total days descending
sorted_people = sorted(person_days.items(), key=lambda x: x[1], reverse=True)
```

Always report skipped records and their reasons (missing dates, missing owner) so the user knows what was excluded.

### Filtering "Incomplete" Records Only

When asked to show only未完成 (incomplete) tasks, filter by Status field:
- **EXCLUDE**: `"Completed"`
- **INCLUDE**: `"Ongoing"`, `"Not started yet"`, `"Blocked"`, `"Expired"`, `None/""` (未设置)

```python
incomplete = [r for r in records if r['fields'].get('Status') != 'Completed']
# For milestone-filtered incomplete:
milestones = ['OTA-V15版本', 'OTA-V16版本', 'OTA-V17版本']
target = [r for r in records
          if r['fields'].get('Milestone') in milestones
          and r['fields'].get('Status') != 'Completed']
```

### Extracting Estimated Days from Project Names
Bitable project names often embed effort estimates. Extract them as a fallback when date ranges are missing:
```python
import re

def extract_days_from_name(name):
    patterns = [
        r'(\d+(?:\.\d+)?)\s*D\b',       # "2D", "1.5D"
        r'(\d+(?:\.\d+)?)\s*人天',       # "2人天", "2.5人天"
        r'(\d+(?:\.\d+)?)\s*天\b',       # "2天"
    ]
    for pattern in patterns:
        match = re.search(pattern, name)
        if match:
            return float(match.group(1))
    return None

# Prefer name-embedded days, fall back to date difference
name_days = extract_days_from_name(project_name)
date_days = (end - start) / 86400000 if start and end else None
days = name_days if name_days else date_days
```