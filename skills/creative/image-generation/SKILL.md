---
name: image-generation
category: creative
description: Generate images via AI — supports Google Gemini 3.1 Flash Image Preview (default, via proxy) and Alibaba Cloud DashScope (通义万相) as fallback. Covers text-to-image, image-to-image (reference-guided), batch generation, and character consistency techniques.
trigger: "User asks to generate images, create pictures, draw something, or needs AI image output."
---

# AI Image Generation

Two backends available. **Always try Gemini first** (default), fall back to DashScope if proxy fails.

## Provider Selection

| Provider | Priority | Use When |
|----------|----------|----------|
| **Gemini 3.1 Flash Image Preview** | Default (1st) | All image generation requests |
| **DashScope 通义万相** | Fallback (2nd) | Gemini proxy consistently fails |

---

## Provider 1: Gemini 3.1 Flash Image Preview (Default)

### Configuration
- **Proxy base**: `https://chatdemo.dev.ling.space`
- **Model**: `gemini-3.1-flash-image-preview:generateContent`
- **API key**: `/root/.hermes/cache/gemini_api_key.txt`
- **Auth**: Header `x-goog-api-key: $API_KEY`

### Text-to-Image
```python
import subprocess, base64, json

API_KEY = open("/root/.hermes/cache/gemini_api_key.txt").read().strip()
prompt = "A cute cat sitting on a cloud"

payload = {
    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
}

with open("/tmp/gen.json", "w") as f:
    json.dump(payload, f)

cmd = f'curl -s -X POST "https://chatdemo.dev.ling.space/v1beta/models/gemini-3.1-flash-image-preview:generateContent" -H "x-goog-api-key: {API_KEY}" -H "Content-Type: application/json" -d @/tmp/gen.json'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)

data = json.loads(result.stdout)
parts = data["candidates"][0]["content"]["parts"]
for part in parts:
    if "inlineData" in part and "image" in part["inlineData"].get("mimeType", ""):
        b64_data = part["inlineData"]["data"]
        with open("/tmp/output.png", "wb") as f:
            f.write(base64.b64decode(b64_data))
        print("Saved: /tmp/output.png")
```

### Image-to-Image (Reference-Guided)
When user provides a reference image:
```python
img_path = "/path/to/reference.jpg"
with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

payload = {
    "contents": [{
        "role": "user",
        "parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
        ]
    }],
    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
}
```

### Gemini-Specific Pitfalls
- ✅ Always use `responseModalities: ["IMAGE", "TEXT"]` — without this, no image output
- ✅ Always use JSON file payloads (`-d @file.json`) to avoid escaping issues
- ❌ Don't use `?key=$API_KEY` query param or google-genai SDK
- ⚠️ Rate limit silent failure: `{}` response means hit rate limit, wait 15s+ and retry
- ⚠️ Direct `generativelanguage.googleapis.com` is **BLOCKED** — only proxy works

---

## Provider 2: DashScope 通义万相 (Fallback)

### Configuration
- **Endpoint**: `https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis`
- **Task Query**: `https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}`
- **API Key**: from `OPENAI_API_KEY` in `.env`

### Available Models
| Model | Description | Speed | Quality |
|-------|-------------|-------|---------|
| `wanx2.1-t2i-turbo` | 快速文生图（推荐） | 快 | 高 |
| `wanx2.1-t2i-plus` | 高质量文生图 | 中 | 最高 |
| `wanx-v1` | 基础文生图 | 快 | 中 |

### Text-to-Image (Async Task + Poll)
```python
import json, urllib.request, time

api_key = "sk-xxx"
url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
body = {
    "model": "wanx2.1-t2i-turbo",
    "input": {"prompt": "用户描述"},
    "parameters": {
        "size": "1024*1024",  # 1024*1024, 720*1280, 1280*720
        "n": 1
    }
}
req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "X-DashScope-Async": "enable"
})
resp = json.loads(urllib.request.urlopen(req).read())
task_id = resp["output"]["task_id"]

# Poll for result
for i in range(20):
    time.sleep(5)
    url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    resp = json.loads(urllib.request.urlopen(req).read())
    status = resp["output"]["task_status"]
    if status == "SUCCEEDED":
        urls = [r["url"] for r in resp["output"]["results"]]
        break
    elif status == "FAILED":
        raise Exception(resp["output"]["message"])
```

### DashScope-Specific Pitfalls
- ⚠️ Images stored on OSS with temporary URLs (~24h expiry) — download immediately for permanent storage
- ⚠️ Character consistency: wanx2.1-t2i-turbo struggles with strict character consistency (adds ears/tails, renders 3D shading, misses pupils). Use aggressive `negative_prompt` and post-process with PIL when needed.
- ✅ Chinese prompts work well; English also supported

### Batch Generation Pattern
For 3+ images:
1. Submit all tasks first with `time.sleep(3)` between submissions (avoid 429)
2. Poll all pending tasks every 5s, print status per-task
3. Download immediately when a task completes — don't wait for all

### Celebrity Portraits (DashScope)
- Use full name + iconic visual descriptor
- Specify emotion explicitly
- Include context: "Studio portrait, photorealistic"

---

## Shared: Generate Images from a Document/Webpage

When user asks to generate images based on a document, article, or webpage:

1. **Extract reference images**:
   - Feishu docs: `feishu_doc_read` → look for `img` blocks → download via Bitable/Image API
   - Web pages: `browser_get_images` → pick most relevant
   - PDFs/local: `vision_analyze` or extract programmatically
2. **Use as reference** in image-to-image generation
3. **Prompt strategy**: "Generate [description] with the [object] shown in the reference image. Appearance must match reference exactly."
