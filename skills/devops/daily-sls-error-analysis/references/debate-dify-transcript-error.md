# 辩论 Dify 工作流 Transcript 超限错误

## 错误详情
- **错误码**: Dify API 返回 `{"code": "invalid_param", "message": "transcript in input form must be less than 2048 characters", "status": 400}`
- **Logger**: `app.event.handlers.debate_event_handler` + `app.utils.task_scheduler`（各记录一半）
- **典型消息**: `❌ 辩论报告生成失败: Dify 工作流执行失败: 工作流启动错误: 工作流启动失败: {"code": "invalid_param", ...}`
- **首次发现**: 2026-07-05（46条，集中在03:00-03:30 CST）
- **复发记录**: 07-19(14条) → 08-19(14条) → 09-02(12条) → **09-05(30条，大幅增加)**，间歇性复发且幅度增大，尚未修复
- **特征**: 集中在凌晨03:00时段，task_scheduler 和 debate_event_handler 各记录一半，属于同一错误的两层记录

## 根因
Dify 辩论工作流的 `transcript` input 参数超过 2048 字符限制。辩论过程中产生的对话记录过长，触发 Dify 平台侧的参数校验。

## 修复建议
1. **代码侧**：在调用 Dify 辩论工作流前，对 transcript 做长度截断（限制在 2000 字符以内，保留首尾关键内容）
2. **Dify 侧**：调整工作流 input schema 的 max length 限制（如改为 4096 或更高）
3. **业务侧**：限制单场辩论的轮次数量，避免 transcript 过长

## 查询关键词
- `GetHistograms`: `level: ERROR and "transcript"` 或 `level: ERROR and "invalid_param"` — 需验证可靠性
- `SQL 聚合`: `level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample` — 可靠
