# Wan2.5 and Below — Async Call Protocol

wan2.5-t2i-preview, wan2.2-t2i-flash/plus, wanx2.1-t2i-turbo/plus do NOT support the sync protocol.

## Step 1: Submit Task

```bash
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis
Headers: Authorization: Bearer $KEY, Content-Type: application/json, X-DashScope-Async: enable
Body: {
  "model": "wan2.5-t2i-preview",
  "input": {"prompt": "prompt text"},
  "parameters": {"size": "1024*1024", "n": 1}
}
```

Response: `{"output": {"task_id": "xxx"}, "request_id": "yyy"}`

## Step 2: Poll Task

```bash
GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}
Headers: Authorization: Bearer $KEY
```

Response when done:
```json
{
  "output": {
    "task_status": "SUCCEEDED",
    "results": [{"url": "https://...png"}]
  }
}
```

Statuses: PENDING → RUNNING → SUCCEEDED/FAILED
