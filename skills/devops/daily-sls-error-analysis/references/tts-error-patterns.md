# TTS Error Patterns Reference

## Pattern 1: IPS集中风暴（2026-08-21）
- 单个IPS记录（279555）的description_tts集中失败
- 集中在19:00，1-2小时内，500+条
- 详见 `ips-tts-storm-pattern.md`

## Pattern 2: 多内容分布式TTS失败（2026-10-31）
**10-31实测**: 61条TTS错误（exception_handlers 38 + tts_client 23）

### 失败文本样本
泰迪犬描述、紫薯卷、美人蕉、充电头、三足鬲、塑料小球、铁马护栏、AI魔法相机描述等。

### 关键特征
- **多内容触发**: 分散在多个完全不同的文本内容，非单点
- **全天分布**: 分散在全天多个时段
- **双logger放大**: exception_handlers(38) + tts_client(23)
- **判断**: TTS供应商API整体不稳定，非特定文本问题

### 与Pattern 1对比
| 特征 | IPS集中风暴 | 多内容分布式 |
|---|---|---|
| 触发源 | 单个IPS记录 | 多个不同文本内容 |
| 时间分布 | 集中在1-2小时 | 分散全天 |
| 根因 | 特定文本/IPS问题 | TTS供应商API不稳定 |
| 数量级 | 500+条 | 50-100条 |
