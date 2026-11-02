# Docx Block Write 1770001 — Root Cause & Fix

## Root Cause (Resolved 2026-10-20)

`block_type: 2` uses `"text"` as the field key, **NOT** `"paragraph"`. The skill's examples previously used `"paragraph"` which always returns `1770001`.

Confirmed by GETting existing blocks from a working document — they return:
```json
{"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}}
```

## Working Code Pattern (http.client)

```python
import http.client

conn = http.client.HTTPSConnection("open.feishu.cn")
conn.request("POST", f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
    json.dumps({"children": blocks}),
    {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"})
resp = json.loads(conn.getresponse().read().decode())
conn.close()
```

## Block Type Mapping

| block_type | Field Key | Notes |
|---|---|---|
| 1 | `page` | Root document block |
| 2 | `text` | Paragraph (NOT "paragraph") |
| 3 | `heading1` | Heading level 1 |
| 4 | `heading2` | Heading level 2 |
| 5 | `heading3` | Heading level 3 |

## Tested Variations (All Failed with "paragraph")

- `{"block_type": 2, "paragraph": {"elements": [...]}}` ❌
- With `style: {}` ✅ (still wrong key)
- With `text_element_style` ✅ (still wrong key)
- With `paragraph_style` ✅ (still wrong key)
- With `position` query param ✅ (still wrong key)
- With v2 API endpoint ✅ (still wrong key)

All returned `1770001 "invalid param"`.

## Working Variations (with "text")

- `{"block_type": 2, "text": {"elements": [{"text_run": {"content": "test"}}]}}` ✅
- `{"block_type": 2, "text": {"elements": [{"text_run": {"content": "label", "text_element_style": {"bold": true}}}, {"text_run": {"content": "body"}}]}}` ✅
- `{"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Title"}}]}}` ✅
