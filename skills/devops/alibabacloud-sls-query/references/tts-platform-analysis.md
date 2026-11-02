# TTS 平台分布分析（lingos-oline-echo-sage）

## 字段结构

TTS 请求日志中，平台标识在 `requestBody` JSON 的深层嵌套：
```
requestBody → data → attributes → options → tts_agent
```
示例值：`sensenova_luka_child`, `vocengine_S_vtm97Lap1`, `minimax_dongman_baobao`

## ⚠️ 关键约束

### requestBody 不是索引字段

`requestBody` 未配置为 SLS 索引字段，因此：
- ❌ 不能用 `GROUP BY requestBody` 或 `regexp_extract(requestBody, ...)` 在 analytical SQL 中
- ❌ `requestBody` 在 SQL 中报错：`Column 'requestbody' cannot be resolved`
- ❌ 不能用短关键词（如 `sensenova`）区分平台，该词出现在 Authorization header 签名中，会匹配全部日志
- ❌ 中文字符串（如 `天才童声`）在 SLS GetHistograms 中返回 0

### 覆盖率

不是所有 TTS 请求日志都包含 `requestBody`：
- `tts and msg: request` 的直方图总量 vs 能解析出 tts_agent 的日志量比约 **85-88%**
- 缺失部分是 WebSocket 连接级日志（无请求体）

## 精确统计方法

### 推荐流程

1. **GetHistograms 获取总量**
```python
hist = call_sls("GetHistograms", {
    "project": "leap-online", "logstore": "lingos-oline-echo-sage",
    "query": "tts and msg: request",
    "from": str(from_ts), "to": str(to_ts),
})
total = sum(int(b.get("count", 0)) for b in hist)
```

2. **按分钟分页获取所有日志**
```python
# 先用 10 分钟桶找出活跃分钟
active_minutes = set()
for bucket in range(144):
    wf = base_ts + bucket * 600
    hist = call_sls("GetHistograms", {..., "from": str(wf), "to": str(wf+600)})
    if sum(counts) > 0:
        for m in range(bucket*10, bucket*10+10):
            active_minutes.add(m)

# 对每个活跃分钟，offset 分页取全部
for minute in sorted(active_minutes):
    wf = base_ts + minute * 60
    offset = 0
    while True:
        logs = call_sls("GetLogs", {
            "query": "tts and msg: request",
            "from": str(wf), "to": str(wf+60),
            "line": "100", "offset": str(offset),
        })
        if not logs or len(logs) < 100: break
        offset += 100
```

3. **客户端解析 tts_agent**
```python
import json
for log in logs:
    rb = log.get("requestBody", "")
    if rb:
        rb_json = json.loads(rb)
        tts_agent = rb_json["data"]["attributes"]["options"]["tts_agent"]
```

### 性能参考
- 1440 分钟全量分页提取约需 **8-12 分钟**
- 百万级日志约 5-10 分钟完成

## 已知平台命名规律
- `vocengine_S_<随机ID>`：火山自定义音色（vtm97Lap1, zNn1VJnq1）
- `vocengine_zh_male_<描述>_mars_bigtts`：火山标准音色（天才童声、阳光青年）
- `vocengine_BV<数字>_streaming`：火山流式音色（BV005, BV705）
- `vocengine_ICL_<描述>_tob`：火山 ICL 音色（huoponvhai）
- `minimax_<描述>`：MiniMax 音色（dongman_baobao, cartoon-boy-07）
- `sensenova_<描述>`：感物音色
- `qiaopi_<描述>`：俏皮音色
- `coze_<数字ID>`：扣子平台

## 参考分布（6/3）
火山引擎 ~42%，感物 ~29%，MiniMax ~19%，俏皮 ~8%，扣子 ~1%，其他 ~1%