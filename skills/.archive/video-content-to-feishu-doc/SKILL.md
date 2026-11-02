---
name: video-content-to-feishu-doc
description: Extract content from video (frames + vision analysis) and create a structured Feishu document. Handles video parsing, frame extraction, vision AI analysis, and Feishu Doc API with batched block creation.
version: 1.0.0
---

# Video Content Extraction → Feishu Document

Extract structured content from a video by analyzing frames with vision AI, then create a well-formatted Feishu document with the results.

## When to Use
- User asks to parse/analyze a video and write results to Feishu
- Need to extract subtitles, product info, or key points from a video
- Video content needs to be documented and shared

## Workflow

### Step 1: Get the Video File

#### 1a. Download from Feishu document (video embedded in a docx)
If the user provides a Feishu docx URL containing a video file attachment:

```python
import json, urllib.request

# 1. Get token (read app_id/app_secret from ~/.hermes/config.yaml)
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
data = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode()
req = urllib.request.Request(url, data, headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]

# 2. Extract doc_token from URL (e.g., https://xxx.feishu.cn/docx/CGBUdM55ooo8hexJaiYckaO3npW)
doc_token = "CGBUdM55ooo8hexJaiYckaO3npW"

# 3. Get document blocks to find file blocks
blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks?document_id={doc_token}&page_size=500"
req2 = urllib.request.Request(blocks_url, headers={"Authorization": f"Bearer {token}"})
resp = json.loads(urllib.request.urlopen(req2).read(), strict=False)

# 4. Find block_type=23 (file attachment block)
for item in resp.get("data", {}).get("items", []):
    if item.get("block_type") == 23:
        file_info = item.get("file", {})
        print(f"File: {file_info.get('name')} | token: {file_info.get('token')}")
        file_token = file_info.get("token")

# 5. Download the file
download_url = f"https://open.feishu.cn/open-apis/drive/v1/medias/{file_token}/download"
req3 = urllib.request.Request(download_url, headers={"Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req3) as r, open("/tmp/video.mp4", "wb") as f:
    f.write(r.read())
```

⚠️ **Important**:
- Block type 23 = file attachment in Feishu docx
- File block contains `file.name` and `file.token`
- Download endpoint: `GET /drive/v1/medias/{file_token}/download`
- For video/audio files specifically, this endpoint works. Images use the same endpoint.

#### 1b. Download from Feishu group message (PREFERRED if user sent video in a group)
If the user sent a video as a message attachment in a Feishu group, download it via the Open API:

```python
import yaml, json, urllib.request, os

# 1. Get token
with open(os.path.expanduser('~/.hermes/config.yaml'), 'r') as f:
    config = yaml.safe_load(f)
app_id = config['platforms']['feishu']['extra']['app_id']
app_secret = config['platforms']['feishu']['extra']['app_secret']
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
req = urllib.request.Request(url, data, headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]

# 2. Search group messages for media/file type
# Known chat_ids from channel_directory.json or bot's chat list
chat_id = "oc_xxx"  # the group where user sent the video
url = f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id={chat_id}&page_size=50"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
resp = json.loads(urllib.request.urlopen(req).read())

# Look for msg_type="media" with matching filename
for item in resp.get("data", {}).get("items", []):
    if item.get("msg_type") == "media":
        body = json.loads(item["body"]["content"])
        print(f"Found: {body.get('file_name')} | file_key={body.get('file_key')} | msg_id={item.get('message_id')}")

# 3. Download the file
message_id = "om_xxx"   # from step 2
file_key = "file_v3_xxx"  # from step 2
url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}?type=file"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
resp_data = urllib.request.urlopen(req).read()
with open("/tmp/video.mp4", "wb") as f:
    f.write(resp_data)
print(f"Downloaded {len(resp_data)} bytes")
```

⚠️ **Important**: 
- The download endpoint is `GET /im/v1/messages/{message_id}/resources/{file_key}?type=file` — NOT `/im/v1/files/{file_key}` (that returns error 234008 "app is not the resource sender")
- `msg_type="media"` = video, `msg_type="file"` = document/spreadsheet/etc.
- If the video was sent in a group the bot cannot see, the user needs to re-send it or provide a URL.

#### 1c. Fallback: URL or local cache
- If URL: download with `curl -o /tmp/video.mp4 "URL"`
- Check cache: `/root/.hermes/cache/documents/`

### Step 2: Extract Audio and Transcribe (Whisper)
```bash
# Extract audio from video
ffmpeg -y -i /path/to/video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/video_audio.wav

# Transcribe with Whisper (supports Chinese with --language zh)
whisper /tmp/video_audio.wav --model base --language zh --output_format txt --output_dir /tmp/
```
- Read the resulting `.txt` file for the full transcript
- Clean up obvious ASR errors (homophones, missing punctuation)

### Step 3: Extract Frames (1 per 10-15 seconds)
```bash
mkdir -p /tmp/frames
ffmpeg -i /path/to/video.mp4 -vf "fps=1/10,scale=640:-1" -q:v 3 /tmp/frames/frame_%03d.jpg
```
- For 2min video → ~14 frames
- For longer videos, adjust fps (e.g., `fps=1/30` for 30-second intervals)

### Step 4: Analyze Frames with Vision AI
For each frame, call `vision_analyze`:
```
image_url: /tmp/frames/frame_001.jpg
question: What text/subtitles appear? List all Chinese text, numbered points, headings, and key content.
```

Collect all text/subtitles/headings from each frame into a structured outline.

### Step 5: Compile Structured Summary
Organize findings into sections:
- **Video basic info**: duration, source, speaker, product
- **Content summary**: main theme/topic
- **Detailed sections**: numbered points with context
- **Product features**: if applicable
- **Visual analysis**: scene descriptions, key visual elements
- **Full transcript**: cleaned Whisper output
- **Key takeaways**: actionable summary

### Step 5: Create Feishu Document

#### 5.1 Get Token
Read credentials from `~/.hermes/config.yaml` → `platforms.feishu.extra.app_id` and `app_secret`:
```python
import json, urllib.request
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
data = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode()
req = urllib.request.Request(url, data, headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]
```

#### 5.2 Create Document
```python
url = "https://open.feishu.cn/open-apis/docx/v1/documents"
data = json.dumps({"title": "Document Title"}).encode('utf-8')
req = urllib.request.Request(url, data, method='POST')
req.add_header("Authorization", f"Bearer {TOKEN}")
req.add_header("Content-Type", "application/json; charset=utf-8")
resp = json.loads(urllib.request.urlopen(req).read())
doc_id = resp['data']['document']['document_id']
```

#### 5.3 Add Content Blocks (BATCHED)
⚠️ **CRITICAL**: Add blocks in batches of 2, with 1.5s delay between batches. Larger batches hit 429 rate limits or 1770001 invalid param errors.

```python
import time

def make_text(content):
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": content}}]}}
def make_heading1(content):
    return {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": content}}]}}
def make_heading2(content):
    return {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": content}}]}}

blocks = [make_heading1("Title"), make_heading2("Subtitle"), make_text("Content...")]

batch_size = 2
for i in range(0, len(blocks), batch_size):
    batch = blocks[i:i+batch_size]
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children"
    data = json.dumps({"children": batch}).encode('utf-8')
    req = urllib.request.Request(url, data, method='POST')
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    resp = json.loads(urllib.request.urlopen(req).read())
    time.sleep(1.5)  # Rate limit avoidance
```

#### 5.4 Set Group Edit Permission (MUST DO)
⚠️ **创建文档后必须给群开可编辑权限**，否则群成员无法查看/编辑文档。
Requires `docs:permission.member` scope. If scope not enabled, user must enable at:
`https://open.feishu.cn/app/{app_id}/auth?q=docs:permission.member,docs:permission.member:create`

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

## Block Type Reference
| Block Type | Purpose | Structure |
|------------|---------|-----------|
| 2 | Paragraph text | `{"text": {"elements": [{"text_run": {"content": "text"}}]}}` |
| 3 | Heading 1 | `{"heading1": {"elements": [{"text_run": {"content": "title"}}]}}` |
| 4 | Heading 2 | `{"heading2": {"elements": [{"text_run": {"content": "subtitle"}}]}}` |
| 5 | Heading 3 | `{"heading3": {"elements": [...]}}` |
| 22 | Bullet list | ⚠️ Returns 1770001 errors — use `make_text("• item")` instead |

## Common Pitfalls
- **Feishu docx file download**: For videos/files embedded in a Feishu docx, use `GET /drive/v1/medias/{file_token}/download`. The file_token comes from block_type=23 in the document blocks API. This is different from the group message download endpoint.
- **Feishu video download endpoint**: Use `GET /im/v1/messages/{message_id}/resources/{file_key}?type=file`. Do NOT use `/im/v1/files/{file_key}` — it returns error 234008 "The app is not the resource sender".
- **Feishu message API container_id_type**: Use `chat`, not `one-on-one` (which returns error 230001). For DMs, use the chat_id from the bot's chat list.
- **Xiaohongshu blocked on server**: Server IP is blocked by XHS (error 300012). Cannot use curl/browser/xhs-lib. Only `opencli xiaohongshu` works, but requires local Chrome with Browser Bridge extension connected.
- **OpenCLI extension in headless**: Chrome headless mode on server cannot load OpenCLI extension. Extension needs GUI environment.
- **Batch size > 2**: Feishu API returns 1770001 or 429 errors. Always batch=2 with 1.5s delay.
- **Bullet blocks (type 22) fail**: Block type 22 (bullet) consistently returns 1770001 "invalid param". **Workaround**: Use `make_text("• item text")` instead — renders identically visually. Only use block types 2 (text), 3 (h1), 4 (h2) — these are confirmed stable.
- **Emoji in headings**: Usually works, but if 1770001 occurs, try removing emoji.
- **Permission errors**: `docx:document` needed for creation, `docs:permission.member` needed for sharing. Both must be enabled in Feishu Open Platform.
- **Token reuse**: tenant_access_token expires ~2 hours. Re-fetch if stale.
- **User open_id**: Get from config or previous message API responses. Default: `ou_b1ae70c2ac573b88db4656fcd79482e2`.
- **Document URL**: `https://{domain}.feishu.cn/docx/{doc_id}` — replace domain with user's Feishu tenant domain.