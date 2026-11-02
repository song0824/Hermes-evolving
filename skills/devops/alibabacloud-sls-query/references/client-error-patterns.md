# lingos-online-client-error Error Patterns

Java/React client error logstore (`leap-online`, `cn-shanghai`). Log field: `content` (NOT `message`). No `level` index — search by keyword `ERROR`.

## Known Error Sources (2026-05-23/24 weekend data)

| Source Class | Pattern Keyword | Description | Typical Count/Day |
|---|---|---|---|
| `c.l.os.chat.share.utils.LoggerUtils` | `消息处理异常` | Chat message processing failure (largest source, ~16%) | 1,200-1,600 |
| `c.l.os.chat.share.utils.LoggerUtils` | `Agent请求` | Agent downstream request failure | 500-900 |
| `c.l.o.t.c.i.tts.TTSProvider` | `TTSProvider` / `TTS转换失败` | TTS conversion failure (scattered, unique IDs) | scattered |
| `c.l.o.s.c.a.SpecialPrologueGenerateImpl` | `生成特殊开场白失败` / `开场白内容为空` / `调用大模型生成lingos开场白发生错误` | Prologue generation via LLM failure | ~570 |
| `c.l.o.s.a.a.t.GenerateSpecialPrologueTask` | `scheduled task` + `MyBatisSystemException` | Scheduled prologue task DB errors | ~567 (fixed) |
| `c.l.os.chat.share.utils.LoggerUtils` | `ASR预处理` | ASR preprocessing errors | 2-3 |
| `reactor.core.publisher.Operators` | `Operator called default onErrorDropped` | Reactor unhandled errors | 200-600 |
| `o.s.s.s.TaskUtils` | `scheduled task` + `PersistenceException` | MyBatis DB query exceptions | ~567 |

## Container & Namespace Architecture (Updated 2026-06-24)

Three containers write to this logstore across two namespaces:

| Container | Namespace | Image Version | Role |
|---|---|---|---|
| `lingos-client` | `lingos-online-new` | v312+ | 客户端主服务 (Java/Reactor/Netty) |
| `lingos-admin` | `lingos-online-pre` / `lingos-online-new` | v170-v176 / v308+ | 管理后台/定时任务/LLM开场白生成 (Spring Boot/MyBatis) |
| `lingos-proxy` | `lingos-online-pre` | v170-v176 | 网关代理 (Spring Cloud Gateway) |

⚠️ **pre 命名空间是旧版**，**new 命名空间是新版**。部署日错误量会翻倍（~4,000 → ~9,000/天）。

## Top Error Categories (7-day full scan 2026-06-17 to 2026-06-24)

| Category | GetHistograms Keyword | Count (7d) | % | Primary Container |
|---|---|---|---|---|
| 连接被关闭/AbortedException | `Connection has been closed` / `AbortedException` | 12,781 | 28% | lingos-client |
| JDBC连接池耗尽 (Druid) | `GetConnectionTimeoutException` / `Failed to obtain JDBC Connection` | 5,196 | 11% | lingos-admin |
| 消息处理异常 | `消息处理异常` | 4,355 | 10% | lingos-client |
| 404 错误 | `404` | 2,782 | 6% | 多容器 |
| Spring启动失败 | `Application run failed` / `BeanCreationException` | 2,051 | 4% | lingos-proxy |
| Gateway路由失败 | `routeLocator` | 2,051 | 4% | lingos-proxy |
| Base64解码异常 | `Illegal base64 character` | 80 | 0.2% | lingos-client |

**Key findings**:
- **Druid pool maxActive=20** 太小，定时任务集中触发时直接打满（wait 60s 超时），集中在 lingos-admin
- **lingos-proxy routeLocator Bean 创建失败**导致启动崩溃循环（2,051条 = 启动次数），影响 Gateway 路由
- **连接被关闭**（12,781条）是最大类别，来自 Reactor/Netty 客户端断连后未优雅清理
- **404**（2,782条）需关注是否有路由配置遗漏

## Peak Hour Patterns

- **Morning peaks** (08:00-12:00): Traffic-driven
- **Deploy-day spike**: 新版本部署当天错误量翻倍（6/19: 9,763, 6/20: 8,735），随后逐步回落到基线 ~4,000
- **Night baseline**: ~65-70/hour

## Source Class Extraction Technique

When `GROUP BY substr(content)` returns mostly count=1 entries (unique error messages), extract source class from raw logs:

```python
import re
raw = call_sls("GetLogs", {"query": "ERROR", "line": "50", ...})
classes = {}
for entry in raw:
    content = entry.get("content", "")
    m = re.search(r'ERROR\s+(c\.l\.\S+?)\s+-', content)
    if m:
        cls = m.group(1)
        classes[cls] = classes.get(cls, 0) + 1
```

Common class abbreviations:
- `c.l.o.t.c.i.tts.TTSProvider` → TTS provider
- `c.l.os.chat.share.utils.LoggerUtils` → Chat/Agent message handler
- `c.l.o.s.c.a.SpecialPrologueGenerateImpl` → Prologue generator
- `c.l.o.s.a.a.t.GenerateSpecialPrologueTask` → Scheduled prologue task
- `reactor.core.publisher.Operators` → Reactor error handling
- `o.s.s.s.TaskUtils$LoggingErrorHandler` → Spring scheduler
