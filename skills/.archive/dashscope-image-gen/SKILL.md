---
name: dashscope-image-gen
description: Generate images using Alibaba Cloud DashScope (通义万相) API. Supports text-to-image, image-to-image, and various styles.
trigger: User asks to generate an image, create a picture, draw something, or needs AI image generation.
---

## Configuration

- **API Key**: `sk-683d81eb029a41a08c61a410eb7d6d0a` (from OPENAI_API_KEY in .env)
- **Endpoint**: `https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis`
- **Task Query**: `https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}`

## Available Models

| Model | Description | Speed | Quality |
|-------|-------------|-------|---------|
| `wanx2.1-t2i-turbo` | 快速文生图（推荐） | 快 | 高 |
| `wanx2.1-t2i-plus` | 高质量文生图 | 中 | 最高 |
| `wanx-v1` | 基础文生图 | 快 | 中 |

## Steps to Generate Image

1. **Submit task** (POST):
```python
import json, urllib.request, time

api_key = "sk-683d81eb029a41a08c61a410eb7d6d0a"
url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
body = {
    "model": "wanx2.1-t2i-turbo",
    "input": {"prompt": "用户描述"},
    "parameters": {
        "size": "1024*1024",  # 1024*1024, 720*1280, 1280*720
        "n": 1  # 1-4
    }
}
req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "X-DashScope-Async": "enable"
})
resp = json.loads(urllib.request.urlopen(req).read())
task_id = resp["output"]["task_id"]
```

2. **Poll for result** (GET):
```python
import time
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

3. **Download for permanent storage** (optional):
```python
import urllib.request
urllib.request.urlretrieve(urls[0], "/path/to/save.png")
```

## Parameters

- `size`: 1024*1024 (默认), 720*1280 (竖屏), 1280*720 (横屏)
- `n`: 生成数量 (1-4)
- `prompt`: 图片描述（支持中英文）
- `negative_prompt`: 不想要的内容（可选）

## Examples

- "画一只在太空中的猫" → prompt: "一只猫在太空中漂浮，星星背景，科幻风格"
- "生成产品海报背景" → prompt: "简洁的产品展示背景，渐变色，现代感"
- "画个logo" → prompt: "简约logo设计，几何图形，蓝色主题"

## Character Consistency (Important Pitfalls)

wanx2.1-t2i-turbo **struggles with strict character consistency**. Common violations:
- Always adds ears, tails, helmets, or accessories to blob/simple characters
- Renders characters as 3D with rim lighting, shading, or white outlines
- Misses pupils (renders blank white eyes)
- Gets droplet/particle counts wrong (generates 2 or 4 instead of 3)
- Makes shapes geometric (rounded squares) instead of organic blobs

### Mitigation Strategies

1. **Use negative_prompt aggressively** — list everything the character should NOT have:
```python
"negative_prompt": "3D, render, shading, highlight, rim light, outline, stroke, ears, tail, helmet, hat, accessory, arms, legs, paws, nose, blush"
```

2. **Be extremely explicit** in the positive prompt:
- "solid pure black silhouette with ZERO shading, ZERO highlights, ZERO 3D effects"
- "two small white oval eyes with small black pupil dots in center"
- "NO white outline, NO stroke, NO appendages"
- "exactly three small black ink droplets"

3. **Post-process with PIL** when AI fails (always verify with vision_analyze first):
```python
from PIL import Image, ImageDraw
img = Image.open("image.png")
draw = ImageDraw.Draw(img)
# Add pupils to white eyes
draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill="black")
# Add missing ink droplets
draw.ellipse([x-r, y-r, x+r, y+r], fill="black")
img.save("fixed.png")
```

4. **Use vision_analyze** on every generated image to verify character compliance before presenting to user.

5. **For existing characters**, prefer image-to-image with a reference image instead of text-to-image to maintain consistency.

## Batch Generation Pattern

For generating multiple images (3+), use parallel submission with staggered polling:

1. **Submit all tasks first** with `time.sleep(3)` between submissions to avoid 429
2. **Poll in a loop** — check all pending tasks every 5s, print status per-task
3. **Download immediately** when a task completes — don't wait for all to finish
4. Set poll attempts high (30+) — some tasks take 30-60s

```python
# Submit phase
for i, prompt in enumerate(prompts):
    if i > 0: time.sleep(3)
    # ... submit task, collect task_ids

# Poll phase
for attempt in range(30):
    time.sleep(5)
    for name, task_id in task_ids.items():
        if name in completed: continue
        # ... check status, download if SUCCEEDED
    if all_done: break
```

## Celebrity / Real Person Portraits

wanx2.1-t2i-turbo handles celebrity portraits well with these prompt patterns:
- Use full name + iconic visual descriptor (e.g., "Jackie Chan, the famous martial arts actor with his iconic short black hair")
- Specify emotion explicitly: "laughing heartily with a wide warm smile", "beaming with an enormous joyful smile"
- Include context: "Studio portrait, photorealistic" or "Stadium celebration atmosphere"
- For the object being held, describe relative size: "about half the size of his palm", "fits in one palm"

## Notes

- Images are stored on OSS with temporary URLs (expire in ~24h)
- For long-term storage, download and save to a permanent location
- Chinese prompts work well, English also supported
- Submit batch tasks with delays; poll results sequentially
