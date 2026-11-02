## Echo-Sage TTS/ASR 全量平台分析模式

**适用场景**：用户要求精确全量提取 TTS/ASR 各平台（tts_agent）的 QPS/RPM 数据，拒绝采样估算。

**核心约束**：
- `requestBody` 字段含完整 JSON 请求体（可能 10KB+），导致 GetLogs 即使 line=3 也返回空（响应体超限被 SLS 内部拦截）
- 直方图（GetHistograms）对 ASCII 短关键词可靠，但长中文关键词可能返回 0

### 步骤

#### Step 1: 构建分钟级直方图（找活跃分钟）
```python
# 10 分钟桶预过滤，确定哪些分钟有数据
for bucket in range(144):
    wf = base_ts + bucket * 600
    wt = wf + 600
    hist = GetHistograms(query="tts and msg: request", from=wf, to=wt)
    # 有数据的桶 → 标记其 10 个分钟为活跃
```

#### Step 2: 逐分钟分页抓取（line=100, offset 递增）
```python
for minute in sorted(active_minutes):
    wf = base_ts + minute * 60
    wt = wf + 60
    offset = 0
    while True:
        logs = GetLogs(query="tts and msg: request", from=wf, to=wt, line="100", offset=str(offset))
        if not logs or len(logs) < 100:
            break
        offset += 100
    # 解析每条日志的 requestBody JSON，提取 options.tts_agent
```

#### Step 3: 秒级 QPS 计算
```python
# 对每个 tts_agent，按 __time__ 分组（秒级时间戳）
# peak QPS = max(count per second)
```

#### Step 4: 按提供商汇总
```
sensenova → SenseNova (感物)
minimax   → MiniMax
qiaopi    → Qiaopi (俏皮)
coze      → Coze (扣子)
vocengine → Volcengine (火山引擎)
```

### 关键参数
| 参数 | 值 | 原因 |
|---|---|---|
| query | `tts and msg: request` | 仅统计 HTTP 请求日志，排除内部 TTS 处理日志 |
| line | `100` | 每页 100 条，分钟窗口内分页 |
| 窗口 | 1 分钟 | 足够小避免响应超限，足够大减少 API 调用 |

### ASR 分析同理
- ASR 关键词：`ws/asr`（WebSocket 连接）
- 每条日志 = 1 个唯一请求（无 requestBody 问题）
- 可直接用 `line=100` + offset 分页
