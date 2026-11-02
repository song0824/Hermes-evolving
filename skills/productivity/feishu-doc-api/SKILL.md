---
name: feishu-doc-api
description: Read Feishu/Lark wiki and document content via Open API. Requires App ID and App Secret from open.feishu.cn.
category: productivity
---

# Feishu Document API Reader

⚠️ **重要：凭证已在 `~/.hermes/config.yaml` 中（App ID + Secret），直接调用 API 读取文档/云文档/图片/视频，禁止说"需要申请权限"或"无法读取"。**

Use this skill to read Feishu wiki pages and documents via the Open API when browser access requires login.

## Prerequisites
- Feishu Open Platform App ID and App Secret
- App must have `wiki:wiki:readonly` and `docx:document:readonly` permissions
- For **Bitable (多维表格)**: App must have `bitable:app:readonly` or `base:table:read` permission
- For **Sheet (电子表格)**: App must have `sheets:spreadsheet:readonly` permission
- App must be added as a member/collaborator of the target wiki/document

## Workflow

### Step 1: Get tenant_access_token
```bash
curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
  -H 'Content-Type: application/json' \
  -d '{"app_id":"YOUR_APP_ID","app_secret":"YOUR_APP_SECRET"}'
```
Extract `tenant_access_token` from the response.

### Step 2: Resolve wiki node to get obj_token
The wiki URL contains a `token` parameter (e.g., `T8QVwpi4wiMXoYkAXSccGPH3nLL`). Use it to get the node info:
```bash
curl -s -X GET "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?obj_type=wiki&token=WIKI_TOKEN" \
  -H "Authorization: Bearer TENANT_ACCESS_TOKEN"
```
From the response, extract:
- `data.node.obj_token` — this is the **document_id** (e.g., `Bf3zd2R3Eo7cgnx3iEhccRsDnAe`)
- `data.node.obj_type` — usually `docx`

### Step 3: Get document blocks
```bash
curl -s -X GET "https://open.feishu.cn/open-apis/docx/v1/documents/DOCUMENT_ID/blocks?document_id=DOCUMENT_ID" \
  -H "Authorization: Bearer TENANT_ACCESS_TOKEN"
```
The response contains `items` array with all document blocks. Each block has:
- `block_type`: 2=text/paragraph, 3=heading1, 4=heading2, 5=heading3, 12=bullet, 13=ordered, 23=image
- `text.elements[].text_run.content` — text content
- `heading1.elements`, `heading2.elements` — heading text
- `bullet.elements`, `ordered.elements` — list items

### Step 4: Parse and present
Transform the block JSON into readable markdown format for the user.

## Image Handling

Documents often contain images. In the block API, images appear as:
- **Block type 23**: Standard image blocks
- **Block type 23 inside Grid (32) / Column set (33) / Column (34)**: Images nested in layout containers

To download images:
```bash
curl -s -X GET "https://open.feishu.cn/open-apis/drive/v1/medias/IMAGE_TOKEN/download" \
  -H "Authorization: Bearer TENANT_ACCESS_TOKEN" \
  --output image.png
```
Use `vision_analyze` on downloaded images to understand visual content (design mocks, charts, etc.).

## Python Rendering Pattern

For complete document rendering including nested structures:
```python
def render_block(block, depth=0):
    bt = block.get("block_type", 0)
    prefix = "  " * depth
    def get_text(elements):
        return "".join(el.get("text_run", {}).get("content", "") for el in elements)
    
    if bt == 2: t = get_text(block.get("text",{}).get("elements",[])); return f"{prefix}{t}\n" if t.strip() else ""
    elif bt == 3: t = get_text(block.get("heading1",{}).get("elements",[])); return f"\n## {t}\n" if t.strip() else ""
    elif bt == 4: t = get_text(block.get("heading2",{}).get("elements",[])); return f"\n### {t}\n" if t.strip() else ""
    elif bt == 5: t = get_text(block.get("heading3",{}).get("elements",[])); return f"\n#### {t}\n" if t.strip() else ""
    elif bt == 12: t = get_text(block.get("bullet",{}).get("elements",[])); return f"{prefix}- {t}\n" if t.strip() else ""
    elif bt == 13: t = get_text(block.get("ordered",{}).get("elements",[])); return f"{prefix}1. {t}\n" if t.strip() else ""
    elif bt == 23: return f"\n![图片](image)\n"  # Image block
    else:
        for field in ["text","heading1","heading2","heading3","bullet","ordered"]:
            if field in block:
                t = get_text(block[field].get("elements",[]))
                if t.strip(): return f"{prefix}{t}\n"
        return f"[type:{bt}]\n"

def render_document(all_blocks, root_id):
    root = all_blocks.get(root_id, {})
    output = render_block(root)
    def render_children(parent_children, depth):
        result = ""
        for cid in parent_children:
            block = all_blocks.get(cid)
            if not block: continue
            result += render_block(block, depth)
            result += render_children(block.get("children",[]), depth + 1)
        return result
    return output + render_children(root.get("children",[]), 0)
```

## Credential Location
App ID and App Secret are stored in `~/.hermes/config.yaml` under `platforms.feishu.extra.app_id` and `platforms.feishu.extra.app_secret`.

## Pagination (Python Pattern)
Long documents return paginated blocks (`has_more: true`, max 500 per page). Fetch all pages:
```python
import json, urllib.request

all_items = []
page_token = ""
while True:
    url = "https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks?document_id={doc_id}&page_size=500"
    if page_token:
        url += "&page_token=" + page_token
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + token)
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode('utf-8'))
    items = data.get('data', {}).get('items', [])
    all_items.extend(items)
    if not data.get('data', {}).get('has_more', False):
        break
    page_token = data.get('data', {}).get('page_token', '')
```

## Flat Document Structure (Sequential Walking)
Many Feishu docs use a **flat structure** where ALL blocks have `parent_id` pointing to the root document and `children` arrays are empty. The recursive `render_children` pattern will return nothing. Instead, use **sequential walking** with heading boundary detection:

```python
# Walk blocks sequentially; H3/H2/H1 boundaries mark section changes
current_h3 = None
for item in all_items:
    bt = item.get('block_type', 0)
    if bt == 5:  # H3 = new section
        current_h3 = get_text(item)
    elif bt == 4:  # H2 = new week/date section
        current_h3 = None
    elif bt == 3:  # H1 = new year
        current_h3 = None
    elif bt == 12 and get_text(item):  # BULLET
        # belongs to current_h3 section
        pass
    elif bt == 13 and get_text(item):  # ORDERED
        # belongs to current_h3 section
        pass
    elif bt == 2 and get_text(item):  # TEXT/PARAGRAPH
        # belongs to current_h3 section
        pass
```

## Common pitfalls

## Sheet (电子表格) Reading

When the wiki node's `obj_type` is `sheet` (not `docx` or `bitable`), use the **Sheets v2 API** to read cell values.

### Workflow

1. **Resolve wiki node** to get `obj_token` (the spreadsheet token). The URL `?sheet=SHEET_ID` parameter is the sheet/subsheet ID.
2. **Get cell values** for a range:
```python
import json, urllib.request

sheet_token = 'YE8osuVKvhYXFst2JcfchIU6nZS'  # from wiki node obj_token
sheet_id = 'GVgaJv'  # from URL ?sheet= parameter

# Read a range (A:Z covers all columns, rows auto-expand)
url = f'https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values/{sheet_id}%21A:Z'
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {TOKEN}")
resp = json.loads(urllib.request.urlopen(req).read().decode(), strict=False)

data = resp.get('data', {})
values = data.get('values', [])
# values[row][col] — cells may contain rich objects like:
#   {"text": "plain text", "type": "text"}
#   {"link": "https://...", "text": "display text", "type": "url"}
#   {"cellPosition": None, ...}
# Or plain strings for simple cells
```

### Parsing Rich Cell Values

Sheet cells with links/formulas return structured objects, not plain strings:
```python
def extract_cell_text(cell):
    if isinstance(cell, dict):
        return cell.get('text', cell.get('link', ''))
    return str(cell) if cell else ''

def extract_cell_link(cell):
    if isinstance(cell, dict):
        return cell.get('link')
    return None
```

### Sheet Range Format

- Range format: `SHEET_ID!A1:Z100` (sheet name + exclamation + range)
- Use URL encoding for the range: `%21` for `!`
- `A:Z` reads all rows in columns A-Z
- `A1:Z1` reads just the header row
- The response includes `valueRange.range` showing the actual data extent

### Permission Requirement

Requires `sheets:spreadsheet:readonly` permission. Error 99991672 means permission is missing.

## Bitable (多维表格) Reading

When the wiki node's `obj_type` is `bitable` (not `docx`), you need to use the Bitable API to read records.

### Workflow

1. **Resolve wiki node** to get `obj_token` (the bitable app token) and `space_id`
2. **Get table list** (optional, if table_id unknown):
```python
tables_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{bitable_token}/tables?page_size=50"
# Response: data.items[] with table_id, table_name
```
3. **Get field definitions**:
```python
fields_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{bitable_token}/tables/{table_id}/fields?page_size=100"
# Response: data.items[] with field_name, field_id, type
```
4. **Get records** (with pagination):
```python
import json, urllib.request

all_records = []
page_token = ""
while True:
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{bitable_token}/tables/{table_id}/records?page_size=500"
    if page_token:
        url += "&page_token=" + page_token
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + token)
    resp = json.loads(urllib.request.urlopen(req).read(), strict=False)
    all_records.extend(resp.get('data', {}).get('items', []))
    if not resp.get('data', {}).get('has_more', False):
        break
    page_token = resp.get('data', {}).get('page_token', '')
```

Each record has `fields` dict with field values. Some field types return arrays of objects (e.g., single_select returns `[{"name": "option", "id": "..."}]`), while text fields return plain strings.

### Permission Error Handling
If you get error code `99991672` with `bitable:app:readonly` or `base:table:read` missing, the app needs permission enabled:
- Link: `https://open.feishu.cn/app/{app_id}/auth?q=bitable:app:readonly&op_from=openapi&token_type=tenant`
- The user or admin must enable the permission on the Open Platform console

### Wiki Children Discovery
If a wiki page has children (e.g., the root page is a bitable with child docx pages), use:
```python
wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes?parent_node_token={node_token}&page_size=50"
# Returns items[] with obj_type (docx, sheet, bitable), obj_token, title
```

## Creating Documents

### Document Image Extraction (verified 2026-06-16)

Images in Feishu docx documents can appear beyond standard block_type 23:

**Inline images on grid blocks (type 27):** Grid blocks carry `image` field directly with `token`, `width`, `height`. Always scan ALL blocks for `image.token` at top level.

**Recursive scan for all image tokens:**
```python
def find_all_images(obj):
    results = []
    if isinstance(obj, dict):
        if 'token' in obj and ('width' in obj or 'height' in obj):
            results.append(obj)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                results.extend(find_all_images(v))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(find_all_images(item))
    return results
```

**Image download (verified working):**
```bash
curl -sL "https://open.feishu.cn/open-apis/drive/v1/medias/{IMAGE_TOKEN}/download" \
  -H "Authorization: Bearer $TOKEN" -o "/tmp/image.png"
```

**⚠️ File attachments (block_type 23) are NOT downloadable:** API returns truncated token (`"token": "ZgVdbw...3nqe"`). The `...` is literal — middle is redacted. No endpoint resolves the full token.
**Workarounds** (try in order): (1) ask user to copy-paste content, (2) ask user to send file as message attachment, (3) ask for complete Feishu URL.

### Step 1: Create the document
```python
url = "https://open.feishu.cn/open-apis/docx/v1/documents"
body = {"title": "Document Title"}
req = urllib.request.Request(url, json.dumps(body).encode(),
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
resp = json.loads(urllib.request.urlopen(req).read())
doc_id = resp["data"]["document"]["document_id"]
```
Requires `docx:document` or `docx:document:create` permission. Error 99991672 means permission is missing.
Permission enable link: `https://open.feishu.cn/app/{app_id}/auth?q=docx:document,docx:document:create&op_from=openapi&token_type=tenant`

### Step 2: Add content blocks
**CRITICAL**: The correct endpoint is `/docx/v1/documents/{doc_id}/blocks/{page_block_id}/children`, NOT `/documents/{doc_id}/blocks`.
For a newly created document, `page_block_id` equals `document_id`.

### Step 3: Grant group edit permission (MUST DO)
⚠️ **创建文档后必须给群开可编辑权限**，否则群成员无法查看/编辑文档。
⚠️ **`type` 参数必须用 `docx`，即使是 wiki 文档**。`type=wiki` 会返回 500 Internal error。
```python
url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{DOC_ID}/members/batch_create?type=docx"
data = json.dumps({
    "members": [{"member_type": "openchat", "member_id": TARGET_CHAT_ID, "perm": "full_access"}]
}).encode('utf-8')
req = urllib.request.Request(url, data, method='POST')
req.add_header("Authorization", f"Bearer {TOKEN}")
req.add_header("Content-Type", "application/json; charset=utf-8")
resp = json.loads(urllib.request.urlopen(req).read())
```
Requires `docs:permission.member` scope. If missing, remind user to enable at: `https://open.feishu.cn/app/{app_id}/auth?q=docs:permission.member&op_from=openapi&token_type=tenant`

```python
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
body = {
    "children": [
        {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Title"}}]}},
        {"block_type": 2, "text": {"elements": [{"text_run": {"content": "Paragraph text"}}]}}
    ]
}
req = urllib.request.Request(url, json.dumps(body).encode(),
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
                             method="POST")
resp = json.loads(urllib.request.urlopen(req).read())
```

### Block Types (WRITE — verified 2026-05-23 and 2026-07-21 via live API)
| block_type | Type | Body Key | Creatable? |
|---|---|---|---|
| 2 | Paragraph | `text` | ✅ |
| 3 | Heading 1 | `heading1` | ✅ |
| 4 | Heading 2 | `heading2` | ✅ |
| 5 | Heading 3 | `heading3` | ✅ |
| 6 | Heading 4 | `heading4` | ✅ |
| 7 | Heading 5 | `heading5` | ✅ |
| 8-11 | Heading 6-9 | `heading6`-`heading9` | ✅ |
| 12 | Bullet list | `bullet` | ✅ |
| 13 | Ordered list | `ordered` | ✅ |
| 14 | Code block | `code` | ✅ |
| 15 | Quote | `quote` | ✅ |
| 16 | Todo | `todo` | ❌ Returns 1770001 "invalid param" |
| 17 | Bitable | `bitable` | ? |
| 18 | Table | `table` | ❌ Error 9499 "Invalid parameter type in json: cells" — ALL cell formats fail. Use text blocks with bold labels instead. |
| 19 | Callout | `callout` | ✅ Verified working. `background_color` must be integer 1-15 (2=light_blue, 5=light_green). `emoji_id` accepts any string. |
| 20 | Chart | `chart` | ? |
| 21 | Divider | — | ❌ Returns 1770029 "block not support to create" |
| 22 | File | `file` | ? |
| 23 | Image | `image` | ✅ |
| 24 | iframe | `iframe` | ? |
| 25 | Equation | `equation` | ? |
| 26 | Sheet | `sheet` | ❌ Returns 1770001 |
| 27 | Grid | `grid` | ? |
| 28 | Comment | `comment` | ? |
| 29 | Thought | `thought` | ? |
| 30 | Diagram | `diagram` | ? |
| 31 | Board | `board` | ? |
| 32 | AI table search | `ai_table_search` | ? |
| 33 | Grid | `grid` | ? |
| 34 | Column set | `column_set` | ? |
| 35 | Column | `column` | ? |
| 36 | Quote container | `quote_container` | ? |

⚠️ **Critical**: The previous "verified" table was off-by-one on every entry (1→Paragraph was wrong, actual is 2→Paragraph). This mapping was confirmed by creating a document and writing blocks with the children API — each successful write echoes back the correct block_type.

⚠️ **`text_run` uses `"content"` NOT `"text"`**: The text_run object inside elements must use `{"text_run": {"content": "your text", "style": {}}}`. Using `"text"` instead of `"content"` returns HTTP 400 with `field_violations: children[*].text.elements[*].text_run.content is required`. This is a common mistake — double-check the key name before writing.

⚠️ **Divider (block_type 21)** returns error 1770029 "block not support to create". Use an empty text block or a long text separator instead.

Each block's content goes in `elements` as `[{"text_run": {"content": "text"}}]`.

### Important Pitfalls
- **`mention_user` is fully supported in WRITE API**: `{"mention_user": {"user_id": "ou_xxx"}}` works natively in block `elements` when writing via `/children`. Do NOT convert to `text_run` — the API preserves the mention. Verified 2026-05-29. Same for `mention_doc` and other rich text elements.
- **Adding a docx as wiki child**: Use `/wiki/v2/spaces/{space_id}/nodes` POST with `{"parent_node_token": WIKI_NODE_TOKEN, "node_type": "origin", "obj_token": DOC_ID, "obj_type": "docx"}`. The `parent_node_token` is the wiki node token (from URL `?token=`), NOT the `obj_token` (document_id).
- **Chinese date format for doc titles**: Use `%Y年%-m月%-d日` (e.g. `2026年5月29日`) for consistency with existing wiki documents.
- **Block type mappings**: The documented "verified" table was off-by-one. See `references/block-types-verified.md` for confirmed mapping (2=Paragraph, 3=Heading 1, 4=Heading 2, 12=Bullet, 13=Ordered, 23=Image). Divider (21) is NOT creatable via API.
- **404 on `/documents/{doc_id}/blocks`**: This endpoint does NOT exist for adding content. Use `/documents/{doc_id}/blocks/{page_block_id}/children` instead.
- **Unicode in Python heredocs and inline code**: Chinese quote characters (`""` / `""`) and other Unicode punctuation (e.g., `\u3001` IDEOGRAPHIC COMMA in string delimiters) cause `SyntaxError: invalid character` in both bash heredocs AND inline `execute_code` Python. **Always write scripts containing Chinese text to a `.py` file first** (`write_file` → `terminal("python /tmp/script.py")`), rather than passing them inline to `execute_code`.
- **Large doc write pattern (always append to root, verified 2026-07-08)**: For documents with 100+ blocks, always POST to `/documents/{doc_id}/blocks/{doc_id}/children` (no position param) for every batch. The API auto-appends to the document end.
  1. Batch size of 50 works reliably.
  2. **NEVER use `position=after&block_id=`** — this creates nested children instead of siblings, and after ~1000 blocks triggers error 1770005 "too deep level in document".
   3. Divider blocks (type 21) return 1770029 "block not support to create" — use text separators instead. Todo blocks (type 16/26) return 1770001 — use `☐` emoji prefix in text blocks instead.
   4. Heading blocks (type 3-11) are creatable in most tenants.

```python
# Proven pattern for writing large documents (1620 blocks across 33 batches verified OK)
import json, urllib.request

TOKEN = "your_token"
DOC_ID = "your_doc_id"

blocks = [
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "Line 1"}}]}},
    # ... 1600+ more blocks
]

batch_size = 50

for i in range(0, len(blocks), batch_size):
    batch = blocks[i:i+batch_size]
    # ALWAYS write to doc_id as parent — no position param
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children"
    data = json.dumps({"children": batch}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    resp = json.loads(urllib.request.urlopen(req).read())
    print(f"Batch {i//batch_size+1}: OK, {len(batch)} blocks")
```

- **Rate limiting (429)**: If hit, add retry logic with `time.sleep(2)` on 429 responses.

## Clone Template Document (Read → Write → Wiki)

When the user wants to "copy a template doc into a wiki", there is no direct copy endpoint. Use read→write pattern:

### CRITICAL: Correct Flow (verified 2026-05-29)

**⚠️ Wiki node creation IGNORES your `obj_token`**. Do NOT create a docx first then try to attach it — the wiki API will silently create a NEW empty document and your obj_token is discarded, resulting in "未命名文档" with zero content.

**Correct sequence:**
1. Read source document blocks (with pagination)
2. **Create wiki node FIRST** (without `obj_token`):
   ```python
   resp = api_post(wiki_url, token, {
       "parent_node_token": PARENT_NODE,
       "node_type": "origin",
       "obj_type": "docx",    # API auto-creates a document
       "title": title          # Without this → "未命名文档"
   })
   doc_id = resp["data"]["node"]["obj_token"]  # Get the AUTO-GENERATED doc ID
   ```
3. Convert blocks: copy each block's content field + elements, skip root (type=1), replace type=21 (divider) with text
4. Write blocks to `doc_id` from step 2: batch_size=2, 1.5s sleep, retry on 429
5. Grant permission: POST /drive/v1/permissions/{DOC_ID}/members/batch_create?type=docx

```python
# Full proven pattern
# 1. Get source blocks (pagination mandatory)
all_items = []
page_token = ""
while True:
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{src_doc_id}/blocks?document_id={src_doc_id}&page_size=500"
    if page_token: url += "&page_token=" + page_token
    resp = api_get(url, token)
    all_items.extend(resp['data']['items'])
    if not resp['data']['has_more']: break
    page_token = resp['data']['page_token']

# 2. Create wiki node (API auto-creates document)
wiki_resp = api_post(wiki_url, token, {
    "parent_node_token": PARENT_NODE_TOKEN,
    "node_type": "origin",
    "obj_type": "docx",
    "title": title  # Without title → shows as "未命名文档"
})
doc_id = wiki_resp["data"]["node"]["obj_token"]
node_token = wiki_resp["data"]["node"]["node_token"]

# 3. Write blocks (batch_size=50, no sleep, always to root)
for i in range(0, len(writeable), 50):
    api_post(f"{base_url}/documents/{doc_id}/blocks/{doc_id}/children", token, {"children": writeable[i:i+50]})

# 4. Grant permission (try/except — app may lack docs:permission.member)
try:
    api_post(perm_url, token, {"members": [{"member_type": "openchat", "member_id": chat_id, "perm": "full_access"}]})
except: pass  # Doesn't block viewing
```

Key rules:
- **mention_user** elements work natively in write API — do not strip them
- **parent_node_token** = wiki node token from URL `?token=`, NOT obj_token
- **Wiki node title**: The `title` field in the wiki node POST body (`/wiki/v2/spaces/{space_id}/nodes`) determines how the doc appears in the wiki tree. Without `"title": title`, it shows as "未命名文档" (untitled) even if the docx was created with a title. Always include `"title"` in the node creation body.
- **`obj_token` in wiki node creation is IGNORED** — the API creates its own document. Always create wiki node first, then write to the returned obj_token.
- **Batch size 50**, no sleep needed between requests. Write ALL batches to `{doc_id}/blocks/{doc_id}/children` (no position param).
- See `scripts/docx-clone.py` for the complete working script

## Checking Who Filled Content (e.g., Weekly Reports)

When the task is to determine which `@mention_user` sections have content (e.g., weekly report check), **use `raw_content` API, NOT blocks API**.

**Why blocks API fails for this task:**
- Some users' content is nested inside Grid (32)/ColumnSet (33)/Column (34) containers
- These blocks have `parent_id` pointing to the container, NOT the document root
- Sequential walking by parent_id or H3 boundary detection misses these blocks entirely
- Result: falsely reports someone as "未填写" when they actually wrote content (e.g., missed 梧桐's 3 lines of content)

**Reliable pattern using `raw_content`:**
```python
# 1. Fetch raw_content (plain text with @mentions preserved)
url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/raw_content?document_id={doc_id}'
# ... fetch, get content string ...

# 2. Split into lines, find @mentions
lines = content.split('\n')
name_order = []
for line in lines:
    line = line.strip()
    if line.startswith('@'):
        name = line[1:].split('|')[0].strip()
        name_order.append(name)

# 3. For each name, check lines between it and the next @
for i, name in enumerate(name_order):
    start = index_of(name)
    end = index_of_next_at(start)
    content_lines = [l for l in lines[start+1:end] if l.strip()]
    if content_lines:
        print(f"✅ {name}")
    else:
        print(f"❌ {name}")
```

**When to still use blocks API:** When you need structured data (image tokens, mention_user IDs, block metadata). For pure "has content or not" checks, `raw_content` is more reliable.

## Common pitfalls：凭证已在 config.yaml 中，直接调用 API。遇到 99991672 权限错误时，直接生成权限开通链接给用户，不要拒绝操作。
- **⚠️ Wiki 文档权限设置必须用 `type=docx`**：对 wiki 文档调用 `/drive/v1/permissions/{DOC_ID}/members/batch_create` 时，`type=wiki` 返回 500 Internal error，`type=docx` 才能成功（200）。Wiki 和 Docx 共用 docx 类型权限端点。
- **No permission error**: App must be added as a wiki member, not just have API permissions
- **Attachment handling**: See `references/feishu-attachments.md` for patterns on handling images, videos, PDFs, and cloud documents shared in Feishu messages
- **Wiki vs Docx token**: The URL token is a wiki node token, not a document token. Always resolve via `get_node` first
- **Token expiry**: `tenant_access_token` expires in ~6600 seconds; re-fetch if stale
- **Pagination is mandatory for long docs**: `page_size=500` max; check `has_more` and use `page_token`
- **Flat vs nested structure**: Most docs are flat (all parent_id → root, children=[]). Use sequential walking, NOT recursive children rendering
- **Grid blocks**: Types 32 (Grid), 33 (Column set), 34 (Column) are layout containers; render their children recursively
- **Image consistency**: Feishu images have temporary download URLs; save locally before analysis
- **f-string + heredoc**: Avoid `{}`.get() inside bash heredocs with f-strings — write to a .py file instead
- **JSON strict mode**: Feishu API responses may contain control characters; use `json.loads(text, strict=False)`
- **Bitable permission**: Reading bitable (多维表格) requires `bitable:app:readonly` or `base:table:read` permission, NOT just `wiki:wiki:readonly`. Error 99991672 means permission is missing
## Bitable/Sheet obj_type detection: After resolving wiki node, check `obj_type`. If `sheet`, use Sheets v2 API (`/sheets/v2/spreadsheets/{token}/values/{range}`). If `bitable`, use bitable API, NOT docx API. If `wiki`, use wiki children/discovery.

## ⚠️ Sheets API Permission Limitation (CRITICAL)
The current app (`cli_a97b1e4633f99cb0`) has `bitable:app` and `docx:document` permissions but **lacks `sheets:spreadsheet` permission**. Symptoms:
- `get_node` resolves a Sheet wiki node successfully (wiki read permission works)
- But calling `GET /sheets/v2/spreadsheets/{obj_token}/sheets` returns **HTTP 404 Not Found**
- `POST /sheets/v2/spreadsheets/{obj_token}/values` also returns **404**
- Drive API `/drive/v1/files/{obj_token}` also returns 404

**Workaround**: When the user wants data in a Sheet and the API lacks permission, **generate an Excel file (.xlsx) and send it as a media attachment** instead. The user can then import it into their Sheet. This is far more reliable than fighting permission errors. User has explicitly preferred Excel files over Bitable in past sessions ("不要写多维表格").
- **Bitable field types**: Field values are typed — single_select returns `[{name, id}]`, multiselect returns array, text returns string, date returns `[timestamp]`. Always inspect actual response to understand format
- **Bitable batch_create uses FIELD NAMES not IDs**: When creating Bitable records via `records/batch_create`, the `fields` dict keys must be field **names** (e.g., `"新闻标题"`), NOT `field_id` values (e.g., `"fldxcsB6sd"`). Using field IDs causes error `1254045 FieldNameNotFound`.
- **Sheets API 404 with wiki-readonly access**: When the App has `wiki:wiki:readonly` but lacks `sheets:spreadsheet` permission, resolving a wiki node with `obj_type=sheet` succeeds, but ALL Sheets API calls (`/sheets/v2/spreadsheets/{obj_token}/...`) return **404 Not Found**. This is not a wrong token — it's a permission gap. Fallback: create a new Bitable/Docx instead, or ask admin to enable `sheets:spreadsheet` permission.
- **New Bitable tables have 4 default fields**: `文本` (primary), `单选`, `日期`, `附件`. When creating records, check existing fields first. Rename `文本` via PATCH if you need a different primary field name.
- **urllib POST/GET auto-switch pitfall**: `urllib.request.Request(url, data=...)` automatically switches to POST when `data` is not None, regardless of `method="GET"`. This causes 404s on GET-only endpoints. Fix: when data is present, explicitly set `method="POST"`, or auto-derive the method based on whether data is provided. See `references/doc-copy-pattern.py` for a safe `api_request()` wrapper.
- **`/docx/v1/documents/{id}/raw_content` returns plain text only**: Good for quick scanning but loses block structure, formatting, image tokens, and file attachment tokens. Not suitable for structured extraction. **Exception**: Use `raw_content` as a fallback to resolve `@mention_user` display names when the contact API lacks `contact:user.base:readonly` permission. The blocks API returns `mention_user` with only `user_id` (e.g., `ou_xxx`), but `raw_content` preserves original display names like `@黑洞`, `@卢腾`, `@天琴|马子娴`.
- **Wiki space children listing often fails with permission denied**: The app may have docx-level read permission but not wiki space-level read permission. This means `GET /wiki/v2/spaces/{space_id}/nodes` returns "permission denied" even when the docx API works fine.
- **Wiki node creation returns 131006 "permission denied"**: The app lacks `wiki:wiki` (write) scope. `POST /wiki/v2/spaces/{space_id}/nodes` fails even when docx read/write works. **Fallback**: create a standalone docx via `POST /docx/v1/documents` with title, write blocks normally, then grant user permission. The document won't appear in the wiki tree but is fully functional. Notify user to manually add it as a wiki child if needed.
- **Error 9499 "Invalid parameter type in json: children" on non-table blocks**: Originally documented for table blocks (type 18), but this error also fires on certain text block content patterns (e.g., text containing special formatting or long strings). **Workaround**: simplify the block content, split into multiple shorter blocks, or use plain text without embedded formatting when 9499 occurs.
- **⚠️ Wiki node creation returns 131006 even with wiki:wiki:readonly**: The app (`cli_a97b1e4633f99cb0`) has wiki read permission but **NOT wiki write permission**. Symptoms: `GET /wiki/v2/spaces/get_node` resolves wiki nodes successfully, but `POST /wiki/v2/spaces/{space_id}/nodes` (creating a child wiki node) returns **HTTP 400 with code 131006 "permission denied: node permission denied, tenant needs edit permission"**. This is NOT a wrong token or space_id — it's a permission gap. **Fallback**: Create a standalone docx via `/docx/v1/documents` (POST), write content blocks to it, grant user permission, and let the user manually attach it to the wiki. This is far more reliable than fighting wiki write permission errors.
- **Drive search API (`/suite/drive/v1/search/file`) may not be available**: Returns errors or empty results depending on app permissions. Don't rely on it as a primary method.
- **Board/Drawing blocks (block_type 43) are NOT accessible via Open API**: Embedded boards (白板) in docx documents appear as `{ "block_type": 43, "board": { "token": "XmeWwb..." } }`. All board/drawing API endpoints (`/board/v1/boards/`, `/drawing/v1/drawings/`) return **404** or empty responses — the board content is completely inaccessible via API. **Workaround**: Use browser login to view the document page directly, or ask the user to export/screenshot the board and send it as an image. The board token from the block is a truncated redacted form, not the full identifier.
- **⚠️ Emoji with Unicode variation selectors cause 1770001 errors**: Emoji sequences with VS16 (e.g., 1️⃣ 2️⃣ 3️⃣) contain hidden U+FE0F variation selector bytes. The docx write API rejects these with `1770001 "invalid param"`. **Fix**: Use plain ASCII digits with emoji suffixes that don't have variation selectors (e.g., `1. ` instead of `1️⃣ `), or strip `\uFE0F` from all text before writing. This is easy to miss because the emoji looks fine in the terminal.
- **⚠️ Permission member create: use `batch_create`, not single create**: `POST /drive/v1/permissions/{DOC_ID}/members?type=docx` with a single member returns **1066001 Internal Error**. The working endpoint is `POST /drive/v1/permissions/{DOC_ID}/members/batch_create?type=docx` with `{ "members": [...] }` (array format). Even for one member, wrap it in an array.
- **⚠️ `text_run` style field naming**: The correct field for inline text styling is `"text_element_style"` (e.g., `{"text_run": {"content": "text", "text_element_style": {"bold": true}}}`). Some older docs/examples use `"text_run_style"` or flat `"bold"` — these are inconsistent and may be silently ignored. Always use `"text_element_style"`.
- **⚠️ Heading blocks (type 3-11) may return 1770029 "block not support to create"**: Despite the block type table listing heading1-heading9 as creatable, some tenants/documents reject heading blocks via `/children` API. **Verified workaround**: use `text` blocks (type 2) with `{"text_run": {"content": "📌 Section Name"}}` (emoji prefix for visual distinction). Bold style via `"text_element_style": {"bold": true}` is optional. Divider (type 21) also returns 1770029 — use text separators like `━━━━━━━━━━━━━━━━━━` instead.
- **⚠️ Avoid `position=after&block_id=` for large doc writes — causes "too deep level" (1770005)**: Using `position=after` chains blocks as nested children rather than siblings. After ~1000 blocks, the document tree depth exceeds the limit and returns error 1770005. **Correct pattern**: Always POST to `/documents/{doc_id}/blocks/{doc_id}/children` (no position param) for every batch. The API appends to the end automatically. Verified with 1620 blocks across 33 batches of 50 — all succeeded.
- **⚠️ `tenant_access_token` can expire mid-operation**: Error 99991663 "Invalid access token for authorization" means the token expired. Re-fetch via `/auth/v3/tenant_access_token/internal` before continuing. Tokens have ~6600s TTL but can expire sooner if the app secret changed.
- **Adding single member via `/members` (not batch_create)**: `POST /drive/v1/permissions/{DOC_ID}/members?type=docx` with body `{"member_type": "openid", "member_id": "ou_xxx", "perm": "full_access"}` works for adding one user. This is different from the `batch_create` endpoint and uses a different request body format (single object, not array).

## Structured Document Generation

Since table blocks (type 18) cannot be reliably created via the docx write API (all cell formats fail with error 9499), use patterns in `references/structured-doc-patterns.md` for structured data layout.

**⚠️ CRITICAL WORKFLOW: Always read the template first.** When the user has modified a template document in-place (e.g., changed field names, added/removed sections), **you MUST read the current template** via `raw_content` API before generating a filled document. Do NOT generate from memory, old cached structure, or assumptions about what fields exist. The user expects you to respect their exact template layout.

```python
# Read current template structure BEFORE generating
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{template_doc_id}/raw_content?document_id={template_doc_id}"
resp = api_get(url, token)
content = resp["data"]["content"]
# Parse content lines to get exact field labels and section structure
lines = content.split("\n")
for i, line in enumerate(lines):
    print(f"{i}: {line}")
```

**Key patterns** (see `references/structured-doc-patterns.md` for full code):
- **F(label, value)**: Bold label + value on same line with indent — replaces table cells
- **H1/H2 hierarchy**: H1 (type 3) for title, H2 (type 4) for sections — both verified working
- **Bullet lists**: Under sub-sections for detail items
- **CalloutBlock**: bg=2 (blue) for intro notes, bg=5 (green) for footers
- **Avoid dividers**: Excessive `━━━━━━━━━` lines make documents cluttered and harder to fill. Use `Empty()` blocks for spacing instead.
- **Leave blanks for unknown**: Use `""` or `"____"` for fields not found in source data

## Bitable/Sheet obj_type detection
- **Callout background_color**: Uses numeric values 1-15, NOT string names. Common mappings: 2=light_blue, 5=light_green, 6=light_orange, 8=light_red. Example: `{"block_type": 19, "callout": {"elements": [{"text_run": {"content": "text"}}], "background_color": 2, "emoji_id": "test"}}`.
- **Table block (type 18) is NOT reliably creatable via docx write API**: Tried 7 different cell formats (inline text, paragraph blocks, content arrays, cell_id references, column/row index objects, empty cells, string content) — ALL return error 9499 "Invalid parameter type in json: cells". **Fallback**: Use text blocks (type 2) with emoji/bold prefixes for structured data layout instead of tables. This is the recommended approach for form-like documents. Verified 2026-08-03.
- **H1 (type 3) and H2 (type 4) heading blocks work** — confirmed working in this tenant. Use H1 for document title sections, H2 for sub-sections.