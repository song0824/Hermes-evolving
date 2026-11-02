---
name: alibaba-dashscope-image-gen
category: mlops
description: Generate images using Alibaba Cloud DashScope (通义万相) API — covers wan2.6-t2i (sync), wan2.5/2.2/2.1 (async), regional endpoints, workspace discovery, and common pitfalls.
---

# Alibaba DashScope (通义万相) Image Generation

## Trigger

Use when the user asks to generate images via 阿里云百炼 / DashScope / 通义万相, or when working with wan2.x-t2i / wanx2.x-t2i models.

## Prerequisites

- **DashScope API Key**: `sk-xxxx` format (stored in `~/.hermes/.env` as `OPENAI_API_KEY` or env var `DASHSCOPE_API_KEY`)
- **Workspace ID**: Required for new sync protocol. Discover via response header trick below.

## Regional Endpoints (CRITICAL)

Beijing, Singapore, and Virginia have **independent API Keys and request URLs**. Keys cannot be mixed across regions.

| Region | Base URL | Workspace URL Pattern |
|--------|----------|----------------------|
| 北京 (cn-beijing) | `https://dashscope.aliyuncs.com` | `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com` |
| 新加坡 (ap-southeast-1) | `https://dashscope-intl.aliyuncs.com` | `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com` |
| 弗吉尼亚 (us-east-1) | N/A | `https://{WorkspaceId}.us-east-1.maas.aliyuncs.com` |

## Discovering Workspace ID

If the user provides an API key but not a Workspace ID, make a test request and extract from response headers:

```bash
curl -s -D- -X POST "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -d '{"model":"wan2.6-t2i","input":{"messages":[{"role":"user","content":[{"text":"test"}]}]},"parameters":{"n":1,"size":"1280*1280"}}' 2>&1 | grep -i "x-dashscope-workspace"
```

Response header `x-dashscope-workspace` gives the Workspace ID (e.g., `llm-2mnugdosx628stt0`).

## wan2.6-t2i — HTTP Sync Call (Recommended)

Only wan2.6 supports the new sync protocol. One request, immediate result.

**Endpoint**: `POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`

```json
{
    "model": "wan2.6-t2i",
    "input": {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"text": "prompt text here"}
                ]
            }
        ]
    },
    "parameters": {
        "prompt_extend": true,
        "watermark": false,
        "n": 1,
        "size": "1280*1280"
    }
}
```

**Parameters**:
- `size`: Total pixels in [1280*1280, 1440*1440], aspect ratio [1:4, 4:1]. Default `1280*1280`
  - 1:1 → 1280*1280 | 3:4 → 1104*1472 | 4:3 → 1472*1104 | 9:16 → 960*1696 | 16:9 → 1696*960
- `n`: 1-4 images (default 4). Per-image billing, set to 1 for testing.
- `prompt_extend`: bool, auto-expand prompt
- `negative_prompt`: string, max 500 chars

**Response**:
```json
{
  "output": {
    "choices": [{
      "finish_reason": "stop",
      "message": {
        "content": [{"image": "https://...oss-url...png?Expires=..."}]
      }
    }]
  }
}
```

## wan2.5 and below — HTTP Async Call

wan2.5/2.2/2.1 do **NOT** support the sync protocol. Must use async:

1. Submit task → get `task_id`
2. Poll task status → get result URL

See `references/wan-async-protocol.md` for details.

## ⚠️ Pitfalls

1. **OpenAI-compatible endpoint returns 404**: `/compatible-mode/v1/images/generations` does NOT work for wan2.6-t2i. Use the new protocol endpoint instead.
2. **Async ImageSynthesis SDK fails for wan2.6**: `dashscope.ImageSynthesis.call(model='wan2.6-t2i')` fails with "InvalidParameter: url error". Use the sync HTTP endpoint directly.
3. **Regional key mismatch**: Beijing key on Singapore endpoint → `invalid_api_key`. Singapore key on Beijing endpoint → same. Must use region-matched key+endpoint.
4. **Image URL expiration**: OSS URLs have `Expires` param. Download immediately after generation.
5. **Prompt length**: Max 2100 characters for positive prompt, 500 for negative prompt.
6. **Only single `text` in content**: Passing multiple text objects or omitting text causes errors.

## Quick Test Script

See `scripts/wan26-test.py` for a ready-to-run test script.

## Reference Files

- `references/wan-async-protocol.md` — Async call flow for wan2.5 and earlier models
- `references/regional-setup.md` — Regional endpoint configuration details
- `scripts/wan26-test.py` — Quick test script for wan2.6-t2i generation
