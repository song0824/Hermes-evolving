---
name: google-gemini-imagen
description: Generate images using Gemini 3.1 Flash Image Preview via internal proxy. Supports text-to-image and image-to-image (reference-guided generation). Default model for all image generation.
trigger: User asks to generate images, create pictures, draw something, or needs AI image output.
category: creative
---

# Gemini 3.1 Flash Image Preview — Default Image Generation

## User Preference

**Always use `gemini-3.1-flash-image-preview:generateContent` for ALL image generation by default.**
API key stored at `/root/.hermes/cache/gemini_api_key.txt`.

## Overview

Google Gemini 3.1 Flash with image output capability. Supports:
- **Text-to-image**: Pure prompt-based generation
- **Image-to-image**: Reference-guided generation with a reference image + prompt describing what to generate
- **Document-aware**: When user asks to generate images based on a document/webpage, first extract images from that document, then use them as reference for image-to-image generation

## Working Configuration (Verified)

**Proxy base**: `https://chatdemo.dev.ling.space`
**Model**: `gemini-3.1-flash-image-preview:generateContent`
**Endpoint**: `/v1beta/models/gemini-3.1-flash-image-preview:generateContent`
**Auth**: Header `x-goog-api-key: $GEMINI_API_KEY`

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

When the user provides a reference image or asks to generate based on an image:

```python
import subprocess, base64, json

API_KEY = open("/root/.hermes/cache/gemini_api_key.txt").read().strip()
img_path = "/path/to/reference.jpg"

with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

prompt = "成龙 laughing while holding the device shown in the reference image. Device appearance matches exactly."

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

with open("/tmp/gen.json", "w") as f:
    json.dump(payload, f)

cmd = f'curl -s -X POST "https://chatdemo.dev.ling.space/v1beta/models/gemini-3.1-flash-image-preview:generateContent" -H "x-goog-api-key: {API_KEY}" -H "Content-Type: application/json" -d @/tmp/gen.json'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)

# Same response parsing as text-to-image above
```

### Batch Generation (Multiple Images)

```python
import time

for i, (prompt, name) in enumerate(prompts):
    if i > 0:
        time.sleep(15)  # 15s cooldown between requests
    # ... generate with payload ...
```

**⚠️ Rate limits**: 15s+ cooldown between requests. If response is empty `{}` or < 1000 chars, treat as rate limit and retry after longer delay.

## Workflow: Generate Images from a Document/Webpage

When user asks to generate images based on a document, article, or webpage:

1. **Extract reference images** from the document:
   - For Feishu docs: use `feishu_doc_read` to get content, look for `img` blocks with `image_key`, download via Bitable/Image API
   - For web pages: use `browser_get_images` to list all images on the page, pick the most relevant ones
   - For PDFs/local files: use `vision_analyze` or extract images programmatically
2. **Use extracted images as reference** in image-to-image generation
3. **Prompt strategy**: "Generate [description] with the [object/product] shown in the reference image. The [object] appearance must match the reference exactly."

## Pitfalls

- ✅ Always use `responseModalities: ["IMAGE", "TEXT"]` — without this, no image output
- ✅ Always use JSON file payloads (`-d @file.json`) to avoid escaping issues
- ✅ Base64-encode reference images and include in `parts` as `{"inline_data": {"mime_type": "...", "data": "..."}}`
- ❌ Don't use Imagen 4.0 (`imagen-4.0-generate-001:predict`) — it has aggressive rate limits and doesn't support image-to-image
- ❌ Don't use `?key=$API_KEY` query param
- ❌ Don't use google-genai SDK
- ⚠️ Response format: `data["candidates"][0]["content"]["parts"]` — iterate parts looking for `inlineData` with image mimeType
- ⚠️ Rate limit silent failure: `{}` response means hit rate limit, wait longer and retry
- ⚠️ Reference images should be clear, well-lit, and show the object from the desired angle

## ⚠️ Network Constraints

- Direct access to `generativelanguage.googleapis.com` is **BLOCKED**
- Only `https://chatdemo.dev.ling.space` proxy works
- If proxy consistently fails, fall back to DashScope (`dashscope-image-gen` skill)