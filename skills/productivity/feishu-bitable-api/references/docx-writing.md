# Feishu Docx Block Writing API

Reference for creating/writing content to Feishu docx documents via Open API. Used when outputting bitable analysis results.

## Create Document
```bash
curl -X POST "https://open.feishu.cn/open-apis/docx/v1/documents" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"title": "Document Title"}'
# Returns: {document_id, revision_id, title}
```

## Block Types
- `2` = Text paragraph (text block)
- `32` = Divider (horizontal line)

## Create Text Block
```json
{
  "block_type": 2,
  "text": {
    "elements": [
      {
        "text_run": {
          "content": "Hello World",
          "text_element_style": {
            "bold": false,
            "inline_code": false,
            "italic": false,
            "strikethrough": false,
            "underline": false
          }
        }
      }
    ]
  }
}
```

**⚠️ Critical pitfall**: Use `content` field (NOT `text`) inside `text_run`. The API returns field validation error 99992402 if you use `text`.

## Create Divider Block
```json
{
  "block_type": 32,
  "divider": {}
}
```

## Append Blocks
First batch (empty document):
```bash
curl -X POST "https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"children": [...]}'
```

Subsequent batches (append after last block):
```bash
curl -X POST "https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{last_block_id}/children?position=after" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"children": [...]}'
```

**Batch size**: Use 50 blocks per batch. Larger batches risk timeout.

## Get Last Block ID
To find the true last block ID (needed for appending), paginate through all children:
```python
page_token = ""
last_id = None
while True:
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=50"
    if page_token: url += f"&page_token={page_token}"
    resp = terminal(f'curl -s "{url}" -H "Authorization: Bearer {token}"')
    data = json.loads(resp["output"])
    items = data.get("data", {}).get("items", [])
    if not items: break
    last_id = items[-1].get("block_id")
    if not data.get("data", {}).get("has_more"): break
    page_token = data["data"].get("page_token", "")
# last_id is now the true last block
```

## Set Document Permission (add member)
```bash
curl -X POST "https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_id}/members?type=docx" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"member_type": "openid", "member_id": "{open_id}", "perm": "full_access"}'
```

## Common Errors
- **99992402** (field validation failed): Usually means `text` instead of `content` in text_run, or missing required field.
- **1770029** (block not support to create): Certain block types (like heading1 with block_type 1) can't be created via children endpoint. Use text block (type 2) with bold style instead.
- **99991663** (Invalid access token): Token expired mid-session. Re-fetch via `/auth/v3/tenant_access_token/internal` and retry.
- **1770005** (too deep level in document): Occurs when using `position=after` chaining with many batches over an existing document. **Fix**: Always write to `{doc_id}/blocks/{doc_id}/children` for every batch (not position=after). This appends to the end of the document regardless of existing content, avoiding nesting depth issues.

## Extracting Estimated Days from Project Names
Bitable records often embed estimated effort in the project name. Use this pattern to extract it:
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
```
Combine with date-based calculation: prefer name-embedded days (more accurate), fall back to date difference.
