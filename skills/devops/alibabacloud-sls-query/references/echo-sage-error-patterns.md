# Echo-Sage (lingos-oline-echo-sage) 错误模式

## Logstore 信息

| 字段 | 值 |
|---|---|
| Project | `leap-online` |
| Logstore | `lingos-oline-echo-sage`（⚠️ **oline** 不是 online） |
| Region | `cn-shanghai` |
| 容器 | `echo-sage` |
| 字段 | `__time__`, `level`, `msg`, `content`, `chainId`, `time` |
| 无此字段 | `logger`, `message`, `exception` |

## 查询注意事项

- `level: error`（**小写**）才能匹配，`level: ERROR` 返回 0
- 无 `logger` 字段，analytical SQL 中 `GROUP BY logger` 不可用
- 错误分类依赖 `msg` 字段 + `content` 内容模式匹配
- 日均日志量：1700万-3600万（随用户活跃度波动）

## 主要错误类型

### 1. ASR 火山引擎超时（~60-90%）

**msg**: `asr-volcengine`

```
server error, code: 45000081, message: {"error":"[Timeout waiting next packet] waiting next packet timeout: 8.000000 seconds, session has ended"}
```

- 客户端音频流中断，8秒未收到新数据包，火山ASR服务端主动断开
- **根因**：客户端网络不稳定 / 麦克风中断 / 弱网环境
- 集中在用户活跃高峰（08:00、16:00、20:00）

## TTS 错误（~10-40%）

**msg**: `TTS`

> ⚠️ 如需分析 TTS **各平台分布**（sensenova/火山/MiniMax 等），见 `references/tts-platform-analysis.md`。

| 子类型 | content 模式 | 说明 |
|---|---|---|
| context deadline exceeded | `Post "https://openspeech.bytedance.com/api/v3/tts/unidirectional": context deadline exceeded` | 火山TTS API 请求超时 |
| GOAWAY | `http2: server sent GOAWAY and closed the connection` | minimax 提供商 HTTP/2 连接关闭 |
| 502 Bad Gateway | `request volcengine v3 tts failed, status: 502` | 火山引擎 502 |
| empty audio | `tts return empty audio bytes, word: ...` | 多语言混合文本（如俄语混中文）导致空音频 |
| file smaller than threshold | `sensenova model checkTTSResult failed: file smaller than threshold` | sensenova_model 返回音频过小（~44字节） |
| JSON解析失败 | `invalid character '<' looking for beginning of value` | TTS返回了HTML而非JSON |

### 3. ASR Processor/Handler（<2%）

**msg**: `asr-processor` / `asr-handler`

```
provider write audio failed, error: use of closed network connection
handler pong message, reset daedline failed, error: set tcp ...: use of closed network connection
```

- 通常是 ASR 45000081 超时的连锁反应

## 典型错误率参考

| 日期 | 总日志量 | ERROR数 | 错误率（/10万） |
|---|---|---|---|
| 5.28 | 1,704万 | 2,366 | 13.9 |
| 5.29 | 1,943万 | 3,593 | 18.5 |
| 5.30 | 3,618万 | 8,596 | 23.8 |
| 5.31 | 3,564万 | 5,959 | 16.7 |
| 6.01 | 2,889万 | 4,093 | 14.2 |
| 6.02 | 1,757万 | 4,297 | 24.5 |
| 6.03 | 1,198万 | 3,291 | 27.5 |

- 用户量少时错误率反而更高（6.03: 27.5/10万）
- TTS 错误在晚间 20:00 可能集中爆发

## 分析工作流

```python
# 1. 获取每日 ERROR 总量
hist = call_sls("GetHistograms", {
    "project": "leap-online",
    "logstore": "lingos-oline-echo-sage",
    "query": "level: error",  # 注意小写
    "from": str(from_ts), "to": str(to_ts),
})

# 2. 采样分类（不能用 SQL GROUP BY logger）
logs = call_sls("GetLogs", {
    "project": "leap-online",
    "logstore": "lingos-oline-echo-sage",
    "query": "level: error",
    "from": str(from_ts), "to": str(to_ts),
    "line": "100",
})
# 按 msg 字段分类
from collections import Counter
msg_counts = Counter(log.get("msg", "") for log in logs)

# 3. 按 content 模式进一步细分
for log in logs:
    content = log.get("content", "")
    if "45000081" in content: ...  # ASR timeout
    elif "context deadline exceeded" in content: ...  # TTS timeout
    elif "empty audio" in content: ...  # TTS empty
    elif "GOAWAY" in content: ...  # HTTP/2 GOAWAY
```
