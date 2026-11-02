# 中间件风暴与恢复模式（2026-07-06 → 2026-07-07）

## 风暴日（07-06）特征

| 指标 | 数值 | 说明 |
|---|---|---|
| 总Error | 25,625 | 历史最高之一 |
| signature_base | 24,511 (95.7%) | Dify(12,101) + DataCard(12,209) 几乎1:1 |
| 峰值时段 | 15:00-17:00 | 16:00达10,095条/小时 |
| /health路径 | 110条 (0.4%) | 主要影响真实API请求 |
| root logger | 55条 | Dify HTML 500(8) + MQTT并发(3) + 微信40029(20) |
| amap_client | 48条 | 高德地图NoneType.stream |

## 恢复日（07-07）特征

| 指标 | 07-07 | 07-06 | 变化 |
|---|---|---|---|
| 总Error | 748 | 25,625 | -97.1% |
| signature_base | 222 | 24,511 | -99.1% |
| Dify中间件 | 113 | 12,196 | -99.1% |
| DataCard中间件 | 115 | 12,302 | -99.1% |
| Internal Server Error | 6 | 368 | -98.4% |
| Unhandled ISE | 2 | 31 | -93.5% |
| ASGI异常 | 0 | 18 | -100% |
| amap_client | 0 | 48 | -100% |
| 微信40029 | 0 | 20 | -100% |

## 恢复信号识别

当看到以下信号**同时出现**时，可判定中间件风暴已恢复：
1. **signature_base 下降 >99%**（从万级降至百级以内）
2. **Dify+DataCard 比例仍接近1:1**（说明中间件逻辑正常，只是不再大规模触发）
3. **Unhandled ISE 和 ASGI异常归零或接近归零**
4. **task_scheduler 重新成为 #1 Logger**（恢复正常的业务失败主导模式）
5. **上午/下午时段（08-17）Error大幅下降**（风暴主战场）

## 残留问题追踪

风暴恢复后仍持续的错误（需单独排查）：
- `NoneType.stream`：54条/天，跨3个logger（weapp_index、task_scheduler、api端点），持续3周+
- `audio_generator_scheduler`：24条，TTS转换异常，呈U型复发（21→6→24）
- TTS相关（tts_client + audio_generator_scheduler）：合计42条，需关注

## 根因推测

07-06风暴与Dify平台HTML 500错误时间重叠（15:00-17:00），且Dify返回HTML而非JSON格式。推测：
1. Dify平台阶段性不可用 → 中间件等待超时 → 大量"No response returned"
2. 线程池耗尽级联 → 影响所有经过中间件的请求
3. Dify恢复后（07-07），中间件风暴自然消除

## 部署版本

| 日期 | 版本 |
|---|---|
| 07-07 | production-168886-v356 |
| 07-06 | 未知（采样时段无ERROR日志或版本信息缺失） |
