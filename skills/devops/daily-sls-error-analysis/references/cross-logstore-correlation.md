# Cross-Logstore Error Correlation Pattern

## Problem
Errors in `ling-server` (e.g., `task_scheduler` reports "Dify工作流执行失败") often have their **root cause** in `lingos-dify` (e.g., Volcengine API 50429 rate limiting). Single-logstore analysis misses the connection.

## Workflow

### Step 1: Find error timestamps in `lingos-dify`
```
project: leap-online, logstore: lingos-dify
query: "50429" (or specific error code)
```
Returns timestamps like `1781768500` (2026-06-21 17:41:40 CST).

### Step 2: Find active agents near those timestamps
Search `lingos-dify` for ALL logs within ±10 seconds of the error timestamp:
```
query: "*", from: ts-10, to: ts+10, line: 50
```
Parse `content` JSON for `agentName` field. The error log itself may have empty `agentName`, but neighboring logs (same workflow run) will have it.

**Example**: At ts 1781768500, neighboring logs revealed `agentName: 角色节日开场白生成器`.

### Step 3: Correlate with `ling-server`
Search `ling-server` for `task_scheduler` errors around the same timestamps:
```
query: "app.utils.task_scheduler and Dify工作流执行失败", from: ts-300, to: ts+300
```

### Step 4: Determine the chain
- `lingos-dify` shows **technical root cause**: `火山文生图任务提交接口调用异常, code: 50429` (API rate limit)
- `ling-server` shows **business impact**: `Dify工作流执行失败: 获取任务结果超时，执行时间: 304.59秒`

## Key Finding (2026-06-21)
`角色节日开场白生成器` workflow triggered Volcengine text-to-image API rate limiting (50429) → Dify couldn't get results → task_scheduler waited 300s and timed out → 2,929 failures in one day (vs normal 255-779).

## Pitfall
- Error logs in `lingos-dify` often have empty `agentName`, `agentId`, `model`, `title` fields. You MUST search neighboring logs to find the workflow name.
- `lingos-dify` `content` field is nested JSON: `{"content": "实际错误消息", ...}`. Parse it to get the inner `content`.
