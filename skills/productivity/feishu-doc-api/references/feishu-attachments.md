# Feishu Attachment Handling Patterns

## Image Attachments in Messages

When a user sends an image in a Feishu group chat:
1. The message contains `msg_type='image'` with an `image_key`
2. Download via: `GET /open-apis/im/v1/images/{image_key}`
3. Use `vision_analyze` on the downloaded file

```python
import json, urllib.request

url = f"https://open.feishu.cn/open-apis/im/v1/images/{image_key}"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {token}")
resp = urllib.request.urlopen(req)
with open("/tmp/feishu_image.jpg", "wb") as f:
    f.write(resp.read())
```

## Video Attachments — LIMITATION

Video files (`.mp4`, `.mov`, etc.) sent as attachments in Feishu group chats **cannot be retrieved via the `/im/v1/messages` API**:
- They do NOT appear as `msg_type='file'` or `msg_type='video'` in the message list
- The `file_key` / `video_key` is NOT returned in the message body
- Pagination through all messages will not surface them
- Only image attachments (`msg_type='image'` with `image_key`) are accessible

**Workarounds** (in order of preference):
1. User provides a local file path (already on server) → use `ffmpeg` to extract frames → `vision_analyze`
2. User provides a publicly accessible download URL → download → analyze
3. Ask user to re-upload as a cloud document attachment (which can be downloaded via Drive API)

## PDF/File Attachments

Files attached to messages:
- `msg_type='file'` messages contain `file_key`
- Download via: `GET /open-apis/im/v1/files/{file_key}/download`
- For PDFs, use `ocr-and-documents` skill for text extraction

## Cloud Document Attachments

When a document is shared via a wiki link:
1. Extract the wiki token from URL (`?token=xxx`)
2. Use `wiki/v2/spaces/get_node` to resolve to `obj_token` and `obj_type`
3. Based on `obj_type`, call the appropriate API:
   - `docx` → `/docx/v1/documents/{doc_id}/blocks`
   - `bitable` → `/bitable/v1/apps/{app_token}/tables/{table_id}/records`
   - `sheet` → `/sheets/{sheet_token}/values`

## Docx-Embedded File Attachments (⚠️ LIMITED)

When a .md / .pdf / other file is attached **inside** a Feishu docx document (block_type 23):
- The API returns a **truncated token**: `"token": "ZgVdbw...3nqe"` (middle redacted with literal `...`)
- **No API endpoint** can resolve the full token
- `/docx/v1/documents/{id}/raw_content` also omits file attachment tokens
- Drive search and wiki traversal often fail due to permissions

**Workarounds** (try in order):
1. Ask user to copy-paste the file content into chat
2. Ask user to send the file as a message attachment (downloadable via message APIs)
3. Ask user for the complete Feishu Drive URL of the file
4. If in same wiki space, try wiki children listing (may fail with permission denied)

**Image extraction from docx IS supported** — see `feishu-doc-api` SKILL.md for patterns. Only file attachments are affected by this limitation.
