# Echo-Sage TTS 平台分布

## TTS 请求日志结构

每条 TTS HTTP 请求日志（`msg: request`）的 `requestBody` 字段包含完整 JSON：

```json
{
  "data": {
    "type": "tts",
    "attributes": {
      "id": "...",
      "text": "...",
      "options": {
        "is_resource_public": false,
        "speed_ratio": 0.95,
        "tts_agent": "sensenova_luka_child"
      }
    }
  }
}
```

**关键字段**: `data.attributes.options.tts_agent` — 唯一标识 TTS 平台/音色。

## ⚠️ `requestBody` 不是 SLS 索引字段

`requestBody` 未配置为 SLS 索引列，analytical SQL 中 `GROUP BY requestBody` 或 `regexp_extract(requestBody, ...)` 会报错：
```
Column 'requestbody' cannot be resolved
```

**正确做法**: 用小时间窗口 + offset 分页拉取原始日志，在客户端解析 `requestBody` JSON 提取 `tts_agent`。

## 精确统计工作流（全量）

当需要 **精确的** 各平台请求量（而非采样估算）时：

```python
# 步骤 1: 构建分钟级直方图，确定哪些分钟有数据
active_minutes = set()
for bucket in range(144):  # 144 x 10-min buckets
    hist = GetHistograms("tts and msg: request", bucket_start, bucket_end)
    if hist.total > 0:
        for m in range(bucket*10, bucket*10+10):
            active_minutes.add(m)

# 步骤 2: 对每个有数据的分钟，用 offset 分页拉取全部日志
agent_counts = {}
agent_sec_data = {}  # agent -> {timestamp -> count}
for minute in sorted(active_minutes):
    offset = 0
    while True:
        logs = GetLogs("tts and msg: request", minute_start, minute_end,
                       line="100", offset=str(offset))
        if not logs or len(logs) == 0:
            break
        for log in logs:
            rb = json.loads(log["requestBody"])
            agent = rb["data"]["attributes"]["options"]["tts_agent"]
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            agent_sec_data[agent][log["__time__"]] += 1
        offset += 100
        if len(logs) < 100:
            break

# 步骤 3: 计算峰值 QPS
for agent, sec_data in agent_sec_data.items():
    peak_qps = max(sec_data.values())  # 每秒最大请求数
```

## 6/3 精确平台分布（78 个平台）

### 按提供商汇总

| 提供商 | 总量 | 占比 | 均 QPS |
|---|---|---|---|
| Volcengine (火山引擎) | 194,342 | 42.1% | 2.25 |
| SenseNova (感物) | 133,921 | 29.0% | 1.55 |
| MiniMax | 89,346 | 19.4% | 1.03 |
| Qiaopi (俏皮) | 38,603 | 8.4% | 0.45 |
| Coze (扣子) | 4,455 | 1.0% | 0.05 |

### Top 15 平台

| 平台 | 总量 | 占比 | 峰值 QPS |
|---|---|---|---|
| sensenova_luka_child | 133,921 | 29.0% | 28 |
| vocengine_S_vtm97Lap1 | 68,761 | 14.9% | 45 |
| minimax_dongman_baobao | 50,551 | 11.0% | 38 |
| qiaopi_mengmei | 38,603 | 8.4% | 13 |
| vocengine_天才童声 | 23,612 | 5.1% | 14 |
| vocengine_阳光青年 | 22,417 | 4.9% | 81 |
| vocengine_S_zNn1VJnq1 | 15,531 | 3.4% | 9 |
| vocengine_泼辣女孩 | 14,542 | 3.2% | 17 |
| minimax_cartoon-boy-07 | 11,899 | 2.6% | 22 |
| vocengine_S_puEpT9aq1 | 11,213 | 2.4% | 20 |

**注意**: 全量提取覆盖率为 88.5%（461,377 / 521,482），其余 11.5% 为无 `requestBody` 的日志（如内部 TTS 处理日志、WebSocket 连接日志等）。

## 常见 tts_agent 命名模式

| 模式 | 示例 | 提供商 |
|---|---|---|
| `sensenova_*` | `sensenova_luka_child` | 感物 |
| `vocengine_zh_male_*_mars_bigtts` | `vocengine_zh_male_tiancaitongsheng_mars_bigtts` | 火山-预设音色 |
| `vocengine_zh_female_*_mars_bigtts` | `vocengine_zh_female_zhixingnvsheng_mars_bigtts` | 火山-预设音色 |
| `vocengine_S_*` | `vocengine_S_vtm97Lap1` | 火山-自定义音色 |
| `vocengine_ICL_*_tob` | `vocengine_ICL_zh_female_huoponvhai_tob` | 火山-ICL音色 |
| `vocengine_BV*_streaming` | `vocengine_BV005_streaming` | 火山-流式音色 |
| `minimax_*` | `minimax_dongman_baobao`, `minax_sang_masike1` | MiniMax |
| `qiaopi_*` | `qiaopi_mengmei` | 俏皮 |
| `coze_*` | `coze_7568423452617621558` | 扣子 |
