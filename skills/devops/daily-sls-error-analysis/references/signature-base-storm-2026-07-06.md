# signature_base 中间件大规模风暴模式（2026-07-06）

## 事件概述

2026-07-06 15:00-17:00 CST，ling-server 出现大规模 `app.middleware.signature_base` 错误风暴。

## 数据

| 指标 | 数值 |
|---|---|
| 全天 signature_base 总量 | 24,511 条 |
| 占全天 Error 比例 | 95.7% |
| 15:00-17:00 集中量 | 20,035 条（78.2%） |
| 16:00 峰值 | 10,095 条/小时 |
| Dify 中间件 | 12,101 条 |
| DataCard 中间件 | 12,209 条 |
| /health 路径 | 110 条（0.4%） |

## 错误消息格式

```
❌ [Dify] 捕获中间件异常 - chain_id: <id>, 路径: <path>, 异常时间: <ts>, 错误: No response returned.
❌ [DataCard] 捕获中间件异常 - chain_id: <id>, 路径: <path>, 异常时间: <ts>, 错误: No response returned.
```

## 受影响 Top 接口

| 接口 | 数量 | 占比 |
|---|---|---|
| /device/api/creation/list | 8,307 | 33.9% |
| /device/api/children/info | 5,557 | 22.7% |
| /device/api/moments/list | 2,494 | 10.2% |
| /device/api/app/list | 2,225 | 9.1% |
| /device/api/user/setting/detail | 1,829 | 7.5% |

## 关联信号

- **Dify HTML 500**：同时段 task_scheduler 和 root 出现 4 条 "Dify工作流启动失败: HTML Internal Server Error"
- **Dify+DataCard 比例接近 1:1**：实际失败请求约 ~12,300
- **/health 仅 110 条**：主要影响真实 API 请求
- **版本 v333**：production-167733-v333

## 可能根因

1. **Dify 平台 15:00-17:00 不可用** — Dify 返回 HTML 500
2. **v333 版本引入中间件/连接问题**
3. **连接池/线程池耗尽** — 下游超时导致线程阻塞

## 排查命令

```python
# 验证 Dify/中间件比例
histogram_total('level: ERROR and "Dify"', from, to)
histogram_total('level: ERROR and "DataCard"', from, to)

# 检查 /health 占比
histogram_total('level: ERROR and "/health"', from, to)

# 按路径分组
GetLogs(query='level: ERROR and logger: app.middleware.signature_base | SELECT count(1), regexp_extract(message, "路径: ([^ ,]+)", 1) as path GROUP BY path ORDER BY cnt DESC')
```

## 与 task_scheduler 风暴的区别

| 特征 | task_scheduler 风暴 | signature_base 风暴 |
|---|---|---|
| 占比 | 35-55% | 95%+ |
| 时间 | 凌晨为主 | 任意时段 |
| 根因 | Dify超时/风控 | 下游服务不可达 |
| /health影响 | 无 | 低(0.4%) |
